"""Portable BARS/BWAV codec helpers used by Splatoon Audio Converter."""

from __future__ import annotations

import struct
import wave
import zlib
from pathlib import Path

import numpy as np

from .bars import decode_dsp_channel


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def sinc_resample(pcm: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate:
        return pcm.copy()

    output_frames = round(len(pcm) * target_rate / source_rate)
    ratio = target_rate / source_rate
    radius = 24
    result = np.empty((output_frames, pcm.shape[1]), dtype=np.float64)
    pcm_float = pcm.astype(np.float64)
    tap_offsets = np.arange(-radius + 1, radius + 1, dtype=np.int64)
    block_size = 8192

    for block_start in range(0, output_frames, block_size):
        block_end = min(output_frames, block_start + block_size)
        positions = np.arange(block_start, block_end, dtype=np.float64) / ratio
        centers = np.floor(positions).astype(np.int64)
        indices = centers[:, None] + tap_offsets[None, :]
        distance = positions[:, None] - indices
        window = 0.42 + 0.5 * np.cos(np.pi * distance / radius) + 0.08 * np.cos(
            2.0 * np.pi * distance / radius
        )
        window[np.abs(distance) >= radius] = 0.0
        weights = np.sinc(distance) * window
        weights /= weights.sum(axis=1, keepdims=True)
        clipped = np.clip(indices, 0, len(pcm_float) - 1)
        result[block_start:block_end] = np.einsum(
            "bt,btc->bc", weights, pcm_float[clipped], optimize=True
        )

    return np.clip(np.rint(result), -32768, 32767).astype("<i2")


def write_pcm16_wav(path: Path, pcm: np.ndarray, sample_rate: int) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(pcm.shape[1])
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm.astype("<i2", copy=False).tobytes())


def read_gcae(path: Path):
    data = path.read_bytes()
    if data[:4] != b"GCAE":
        raise ValueError("Invalid audio encoder output")
    version, rate, channels, sample_count = struct.unpack_from("<IIII", data, 4)
    if version != 1:
        raise ValueError(f"Unsupported encoder output version {version}")
    cursor = 20
    entries = []
    for _ in range(channels):
        gain = struct.unpack_from("<h", data, cursor)[0]
        cursor += 2
        coefficients = struct.unpack_from("<16h", data, cursor)
        cursor += 32
        start_context = struct.unpack_from("<hhh", data, cursor)
        cursor += 6
        loop_context = struct.unpack_from("<hhh", data, cursor)
        cursor += 6
        adpcm_size, decoded_count = struct.unpack_from("<II", data, cursor)
        cursor += 8
        adpcm = data[cursor : cursor + adpcm_size]
        cursor += adpcm_size
        decoded = np.frombuffer(data, dtype="<i2", count=decoded_count, offset=cursor).copy()
        cursor += decoded_count * 2
        entries.append(
            {
                "gain": gain,
                "coefficients": coefficients,
                "start_context": start_context,
                "loop_context": loop_context,
                "adpcm": adpcm,
                "decoded": decoded,
            }
        )
    if cursor != len(data):
        raise ValueError("Unexpected data at the end of the encoder output")
    return rate, sample_count, entries


def build_adpcm_bwav(rate: int, sample_count: int, entries: list[dict]) -> bytes:
    channels = len(entries)
    framed_size = ((sample_count + 13) // 14) * 8
    channel_data = [entry["adpcm"].ljust(framed_size, b"\0") for entry in entries]
    crc = zlib.crc32(b"".join(channel_data)) & 0xFFFFFFFF
    header_size = 0x10 + channels * 0x4C
    starts = []
    cursor = align(header_size, 0x40)
    for data in channel_data:
        starts.append(cursor)
        cursor = align(cursor + len(data), 0x40)

    output = bytearray(cursor)
    struct.pack_into("<4sHHIHH", output, 0, b"BWAV", 0xFEFF, 1, crc, 0, channels)
    for channel, (start, entry) in enumerate(zip(starts, entries)):
        header = 0x10 + channel * 0x4C
        layout = 2 if channels == 1 else channel
        struct.pack_into("<HHIII", output, header, 1, layout, rate, sample_count, sample_count)
        struct.pack_into("<16h", output, header + 0x10, *entry["coefficients"])
        struct.pack_into("<II", output, header + 0x30, start, start)
        struct.pack_into("<Iii", output, header + 0x38, 1, -1, 0)
        struct.pack_into("<hhh", output, header + 0x44, *entry["start_context"])
        output[start : start + len(entry["adpcm"])] = entry["adpcm"]
    return bytes(output)


def bars_layout(data: bytes):
    if data[:4] != b"BARS":
        raise ValueError("Invalid BARS file")
    declared_size = struct.unpack_from("<I", data, 4)[0]
    count = struct.unpack_from("<I", data, 0x0C)[0]
    if declared_size != len(data):
        raise ValueError("BARS file size does not match its header")
    table = 0x10 + count * 4
    entries = [struct.unpack_from("<II", data, table + i * 8) for i in range(count)]
    names: list[str] = []
    for amta_offset, audio_offset in entries:
        if data[amta_offset : amta_offset + 4] != b"AMTA":
            raise ValueError("Invalid BARS metadata offset")
        if data[audio_offset : audio_offset + 4] != b"BWAV":
            raise ValueError("Only embedded BWAV audio is supported")
        pointer_field = amta_offset + 0x24
        name_offset = pointer_field + struct.unpack_from("<I", data, pointer_field)[0]
        name_end = data.index(0, name_offset)
        names.append(data[name_offset:name_end].decode("utf-8"))
    return count, table, entries, names


def decode_adpcm_bwav(bwav: bytes) -> tuple[int, np.ndarray, int]:
    channels = struct.unpack_from("<H", bwav, 0x0E)[0]
    rate = struct.unpack_from("<I", bwav, 0x14)[0]
    count = struct.unpack_from("<I", bwav, 0x1C)[0]
    decoded = np.empty((count, channels), dtype="<i2")
    raw_channels = []
    encoded_size = ((count + 13) // 14) * 8
    for channel in range(channels):
        header = 0x10 + channel * 0x4C
        codec = struct.unpack_from("<H", bwav, header)[0]
        start = struct.unpack_from("<I", bwav, header + 0x34)[0]
        coefficients = struct.unpack_from("<16h", bwav, header + 0x10)
        _, hist1, hist2 = struct.unpack_from("<hhh", bwav, header + 0x44)
        if codec != 1:
            raise ValueError("Expected DSP-ADPCM BWAV audio")
        raw = bwav[start : start + encoded_size]
        raw_channels.append(raw)
        decoded[:, channel] = np.asarray(
            decode_dsp_channel(raw, count, coefficients, hist1, hist2), dtype="<i2"
        )
    expected_crc = struct.unpack_from("<I", bwav, 8)[0]
    actual_crc = zlib.crc32(b"".join(raw_channels)) & 0xFFFFFFFF
    if expected_crc != actual_crc:
        raise ValueError("BWAV checksum does not match")
    return rate, decoded, actual_crc
