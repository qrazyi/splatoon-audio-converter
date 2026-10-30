#!/usr/bin/env python3
"""Extract and decode Nintendo BARS/BWAV sound archives used by Splatoon 3."""

from __future__ import annotations

import argparse
import importlib.util
import re
import struct
import wave
from pathlib import Path


DEFAULT_ZSTD_HELPER = Path(__file__).resolve().with_name("zstd_helper.py")


def load_zstd_helper(path: Path):
    spec = importlib.util.spec_from_file_location("splatoon_zstd_helper", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load Zstandard helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Zstd()


def read_bars(path: Path, helper_path: Path) -> bytes:
    raw = path.read_bytes()
    if raw.startswith(b"BARS"):
        return raw
    if raw.startswith(b"\x28\xb5\x2f\xfd"):
        return load_zstd_helper(helper_path).decompress(raw)
    raise ValueError(f"{path} is neither a BARS file nor a Zstandard-compressed BARS file")


def safe_name(value: str, fallback: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_.")
    return value or fallback


def bars_entries(data: bytes, require_bwav: bool = True):
    if len(data) < 0x10 or data[:4] != b"BARS":
        raise ValueError("Invalid BARS header")
    declared_size, count = struct.unpack_from("<II", data, 0x04)[0], struct.unpack_from("<I", data, 0x0C)[0]
    if declared_size != len(data):
        raise ValueError(f"BARS size mismatch: header={declared_size}, actual={len(data)}")

    table = 0x10 + count * 4
    offsets = [struct.unpack_from("<II", data, table + i * 8) for i in range(count)]
    # Hash-table order is not guaranteed to be physical audio order.  Use the
    # next greater BWAV offset as the payload boundary instead of blindly using
    # the next table entry (UI_Static is one archive where those differ).
    sorted_audio_offsets = sorted(audio_offset for _, audio_offset in offsets)
    audio_ends = {
        audio_offset: (
            sorted_audio_offsets[position + 1]
            if position + 1 < len(sorted_audio_offsets)
            else len(data)
        )
        for position, audio_offset in enumerate(sorted_audio_offsets)
    }
    for index, (amta_offset, audio_offset) in enumerate(offsets):
        if data[amta_offset : amta_offset + 4] != b"AMTA":
            raise ValueError(f"Entry {index}: invalid AMTA offset 0x{amta_offset:X}")
        magic = data[audio_offset : audio_offset + 4]
        if (require_bwav and magic != b"BWAV") or magic not in (b"BWAV", b"FWAV", b"FSTP"):
            raise ValueError(f"Entry {index}: unsupported audio {magic!r} at 0x{audio_offset:X}")

        if data[amta_offset + 6 : amta_offset + 8] == b"\x00\x04":
            # Wii U AMTA v4 keeps the event name at the start of its STRG block.
            strg_offset = amta_offset + struct.unpack_from("<I", data, amta_offset + 0x18)[0]
            if data[strg_offset : strg_offset + 4] != b"STRG":
                raise ValueError(f"Entry {index}: invalid STRG block")
            name_offset = strg_offset + 8
        else:
            # AMTA v5 stores this displacement relative to the displacement field itself.
            name_pointer_field = amta_offset + 0x24
            name_offset = name_pointer_field + struct.unpack_from("<I", data, name_pointer_field)[0]
        name_end = data.find(b"\0", name_offset)
        if name_end < 0:
            raise ValueError(f"Entry {index}: unterminated AMTA name")
        name = data[name_offset:name_end].decode("utf-8", "replace")

        audio_end = audio_ends[audio_offset]
        yield index, name, audio_offset, audio_end


def clamp16(value: int) -> int:
    return max(-32768, min(32767, value))


def decode_dsp_channel(
    encoded: bytes,
    num_samples: int,
    coefficients: tuple[int, ...],
    hist1: int,
    hist2: int,
) -> list[int]:
    samples: list[int] = []
    cursor = 0
    while len(samples) < num_samples:
        if cursor >= len(encoded):
            raise ValueError(
                f"Truncated DSP stream: decoded {len(samples)} of {num_samples} samples"
            )
        header = encoded[cursor]
        cursor += 1
        predictor = (header >> 4) & 0x07
        scale = 1 << (header & 0x0F)
        coef1 = coefficients[predictor * 2]
        coef2 = coefficients[predictor * 2 + 1]

        # Nintendo archives may store only the used bytes of the final ADPCM
        # frame. Decode that partial frame instead of requiring seven data
        # bytes after every frame header.
        frame_data = encoded[cursor : cursor + 7]
        for byte in frame_data:
            for nibble in (byte >> 4, byte & 0x0F):
                if nibble >= 8:
                    nibble -= 16
                value = (
                    (nibble * scale << 11)
                    + coef1 * hist1
                    + coef2 * hist2
                    + 1024
                ) >> 11
                value = clamp16(value)
                samples.append(value)
                hist2, hist1 = hist1, value
                if len(samples) == num_samples:
                    return samples
        cursor += len(frame_data)
    return samples


def decode_bwav(bwav: bytes):
    if bwav[:4] != b"BWAV":
        raise ValueError("Invalid BWAV header")
    channels = struct.unpack_from("<H", bwav, 0x0E)[0]
    if not 1 <= channels <= 8:
        raise ValueError(f"Unsupported BWAV channel count: {channels}")

    decoded_channels: list[list[int]] = []
    sample_rate = None
    sample_count = None
    metadata = []
    for channel in range(channels):
        header = 0x10 + channel * 0x4C
        codec = struct.unpack_from("<H", bwav, header)[0]
        rate = struct.unpack_from("<I", bwav, header + 0x04)[0]
        count = struct.unpack_from("<I", bwav, header + 0x0C)[0]
        start = struct.unpack_from("<I", bwav, header + 0x34)[0]
        loop_end = struct.unpack_from("<i", bwav, header + 0x3C)[0]
        loop_start = struct.unpack_from("<i", bwav, header + 0x40)[0]
        if sample_rate is None:
            sample_rate, sample_count = rate, count
        elif (rate, count) != (sample_rate, sample_count):
            raise ValueError("BWAV channels do not share sample rate/sample count")

        if codec == 0:
            end = start + count * 2
            if end > len(bwav):
                raise ValueError("Truncated PCM16 BWAV channel")
            samples = list(struct.unpack_from(f"<{count}h", bwav, start))
        elif codec == 1:
            coefficients = struct.unpack_from("<16h", bwav, header + 0x10)
            hist1, hist2 = struct.unpack_from("<hh", bwav, header + 0x46)
            encoded_size = ((count + 13) // 14) * 8
            samples = decode_dsp_channel(
                bwav[start : start + encoded_size],
                count,
                coefficients,
                hist1,
                hist2,
            )
        else:
            raise ValueError(f"Unsupported BWAV codec {codec} on channel {channel}")
        decoded_channels.append(samples)
        metadata.append({"codec": codec, "start": start, "loop_start": loop_start, "loop_end": loop_end})

    assert sample_rate is not None and sample_count is not None
    return sample_rate, sample_count, decoded_channels, metadata


def write_wav(path: Path, sample_rate: int, channels: list[list[int]]) -> None:
    frames = bytearray()
    for frame in zip(*channels):
        frames.extend(struct.pack(f"<{len(frame)}h", *frame))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(len(channels))
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(frames)
