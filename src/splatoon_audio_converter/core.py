"""Audio engine separated from the desktop UI. No machine-specific paths.

Ported from the project's existing converter; HoianViewer code is not used.
"""
from __future__ import annotations

import math
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import zstandard

from .formats.bars import bars_entries, decode_bwav, safe_name, write_wav
from .formats.dsp import (bars_layout, build_adpcm_bwav, decode_adpcm_bwav,
                          read_gcae, sinc_resample, write_pcm16_wav)

TOOLS_DIR = Path(__file__).resolve().parent / "native"
ENCODER_EXE = TOOLS_DIR / "gcadpcm_encode.exe"
DECODER_EXE = TOOLS_DIR / "nintendo_audio_decode.exe"
STREAM_ENCODER_EXE = TOOLS_DIR / "nintendo_stream_encode.exe"


def _require_native(executable: Path) -> None:
    if sys.platform != "win32":
        raise RuntimeError("Nintendo stream conversion is currently available in the Windows build only.")
    if not executable.is_file() or not (TOOLS_DIR / "VGAudio.dll").is_file():
        raise RuntimeError("The bundled Nintendo audio helper is missing. Re-extract the complete application download.")


class Zstd:
    def decompress(self, data: bytes) -> bytes:
        return zstandard.ZstdDecompressor().decompress(data, max_output_size=512 * 1024 * 1024)

    def compress(self, data: bytes) -> bytes:
        return zstandard.ZstdCompressor(level=3).compress(data)


def read_archive(path: Path) -> bytes:
    data = path.read_bytes()
    if data[:4] in (b"BARS", b"BWAV", b"FSTM"):
        return data
    if data[:4] != b"\x28\xb5\x2f\xfd":
        raise ValueError("This is not a valid BARS, BWAV, or BFSTM audio file.")
    decompressed = Zstd().decompress(data)
    if decompressed[:4] not in (b"BARS", b"BWAV", b"FSTM"):
        raise ValueError("The compressed file does not contain BARS, BWAV, or BFSTM audio.")
    return decompressed


def bars_base_name(name: str) -> str:
    """Remove every accidental BARS suffix from a filename."""
    stem = name
    lowered = stem.casefold()
    while lowered.endswith(".bars.zs"):
        stem = stem[:-8]
        lowered = stem.casefold()
    if lowered.endswith(".bars"):
        stem = stem[:-5]
    return stem or "audio"


def bars_zs_name(name: str) -> str:
    """Return an archive name with exactly one .bars.zs suffix."""
    return bars_base_name(name) + ".bars.zs"


def bwav_name(name: str, compressed: bool = False) -> str:
    stem = name
    while stem.casefold().endswith(".bwav.zs"):
        stem = stem[:-8]
    while stem.casefold().endswith(".bwav"):
        stem = stem[:-5]
    return (stem or "audio") + (".bwav.zs" if compressed else ".bwav")


def bfstm_name(name: str, compressed: bool = False) -> str:
    stem = name
    while stem.casefold().endswith(".bfstm.zs"):
        stem = stem[:-9]
    while stem.casefold().endswith(".bfstm"):
        stem = stem[:-6]
    return (stem or "audio") + (".bfstm.zs" if compressed else ".bfstm")


def pcm_levels(channels: list[list[int]]) -> tuple[float, float]:
    """Return peak and RMS levels in dBFS for decoded PCM16 audio."""
    pcm = np.asarray(channels, dtype=np.float64)
    if pcm.size == 0:
        return -math.inf, -math.inf
    absolute_peak = float(np.max(np.abs(pcm)))
    rms = float(np.sqrt(np.mean(np.square(pcm))))
    peak_dbfs = -math.inf if absolute_peak == 0 else 20.0 * math.log10(absolute_peak / 32768.0)
    rms_dbfs = -math.inf if rms == 0 else 20.0 * math.log10(rms / 32768.0)
    return peak_dbfs, rms_dbfs


def format_dbfs(value: float) -> str:
    return "-inf" if not math.isfinite(value) else f"{value:.1f}"


def read_pcm16(path: Path) -> tuple[int, np.ndarray]:
    import wave

    with wave.open(str(path), "rb") as source:
        if source.getcomptype() != "NONE" or source.getsampwidth() != 2:
            raise ValueError(f"{path}: expected an uncompressed 16-bit PCM WAV")
        channel_count = source.getnchannels()
        if channel_count not in (1, 2):
            raise ValueError(f"{path}: expected mono or stereo, got {channel_count} channels")
        rate = source.getframerate()
        frames = source.getnframes()
        pcm = np.frombuffer(source.readframes(frames), dtype="<i2").reshape(-1, channel_count).copy()
    return rate, pcm


def match_channels(pcm: np.ndarray, target_channels: int) -> np.ndarray:
    if pcm.shape[1] == target_channels:
        return pcm
    if pcm.shape[1] == 1 and target_channels == 2:
        return np.repeat(pcm, 2, axis=1)
    if pcm.shape[1] == 2 and target_channels == 1:
        mixed = np.rint(pcm.astype(np.float64).mean(axis=1))
        return np.clip(mixed, -32768, 32767).astype("<i2")[:, None]
    raise ValueError(f"Cannot convert {pcm.shape[1]} channels to {target_channels}")


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def rebuild_bars(bars: bytes, replacements: dict[str, bytes]) -> bytes:
    count, table, entries, names = bars_layout(bars)
    if not replacements.keys() <= set(names):
        raise KeyError(f"Archive lacks mapped entries: {sorted(replacements.keys() - set(names))}")
    ordered_offsets = sorted(audio for _, audio in entries)
    ends = {
        offset: ordered_offsets[position + 1] if position + 1 < len(ordered_offsets) else len(bars)
        for position, offset in enumerate(ordered_offsets)
    }
    payloads = [bars[audio : ends[audio]] for _, audio in entries]
    first_audio = min(audio for _, audio in entries)
    output = bytearray(bars[:first_audio])
    new_offsets: list[int] = []
    for name, original in zip(names, payloads):
        output.extend(bytes(align(len(output), 0x40) - len(output)))
        new_offsets.append(len(output))
        output.extend(replacements.get(name, original))
    for index, audio_offset in enumerate(new_offsets):
        struct.pack_into("<I", output, table + index * 8 + 4, audio_offset)
    struct.pack_into("<I", output, 4, len(output))
    if count != len(names):
        raise RuntimeError("BARS entry count changed")
    return bytes(output)


def inspect_bwav(bwav: bytes) -> tuple[int, int, int, int, int, int]:
    """Read BWAV headers without decoding potentially huge audio payloads."""
    if len(bwav) < 0x10 or bwav[:4] != b"BWAV":
        raise ValueError("Invalid BWAV header")
    channels = struct.unpack_from("<H", bwav, 0x0E)[0]
    if not 1 <= channels <= 8:
        raise ValueError(f"Unsupported BWAV channel count: {channels}")
    first = 0x10
    codec = struct.unpack_from("<H", bwav, first)[0]
    rate = struct.unpack_from("<I", bwav, first + 0x04)[0]
    count = struct.unpack_from("<I", bwav, first + 0x0C)[0]
    loop_end = struct.unpack_from("<i", bwav, first + 0x3C)[0]
    loop_start = struct.unpack_from("<i", bwav, first + 0x40)[0]
    for channel in range(1, channels):
        header = 0x10 + channel * 0x4C
        channel_codec = struct.unpack_from("<H", bwav, header)[0]
        channel_rate = struct.unpack_from("<I", bwav, header + 0x04)[0]
        channel_count = struct.unpack_from("<I", bwav, header + 0x0C)[0]
        if (channel_codec, channel_rate, channel_count) != (codec, rate, count):
            raise ValueError("BWAV channels do not share codec, sample rate, and sample count")
    return rate, count, channels, codec, loop_start, loop_end


def inspect_nintendo_audio(data: bytes) -> tuple[int, int, int, int, int, int]:
    """Read FWAV/FSTM/FSTP timing from INFO without decoding the sound."""
    magic = data[:4]
    if magic not in (b"FWAV", b"FSTM", b"FSTP") or len(data) < 0x68:
        raise ValueError("Invalid NintendoWare audio header")
    endian = "<" if data[4:6] == b"\xff\xfe" else ">" if data[4:6] == b"\xfe\xff" else None
    if endian is None:
        raise ValueError("Invalid NintendoWare byte order")
    info = struct.unpack_from(endian + "I", data, 0x18)[0]
    if info + 0x20 > len(data) or data[info:info + 4] != b"INFO":
        raise ValueError("NintendoWare INFO block is missing")
    if magic == b"FWAV":
        header = info
        codec = data[header + 8]
        looped = bool(data[header + 9])
        rate = struct.unpack_from(endian + "I", data, header + 0x0C)[0]
        loop_start = struct.unpack_from(endian + "I", data, header + 0x10)[0]
        count = struct.unpack_from(endian + "I", data, header + 0x14)[0]
        channels = struct.unpack_from(endian + "I", data, header + 0x1C)[0]
    else:
        displacement = struct.unpack_from(endian + "I", data, info + 0x0C)[0]
        header = info + 8 + displacement
        if header + 0x10 > len(data):
            raise ValueError("NintendoWare stream metadata is truncated")
        codec = data[header]
        looped = bool(data[header + 1])
        channels = data[header + 2]
        rate, loop_start, count = struct.unpack_from(endian + "III", data, header + 4)
    if not 1 <= rate <= 384000 or count < 1 or channels > 32 or codec > 3:
        raise ValueError("Invalid NintendoWare sample metadata")
    if looped and loop_start >= count:
        raise ValueError("Invalid NintendoWare loop point")
    return rate, count, channels, codec, loop_start if looped else 0, count if looped else -1


@dataclass(frozen=True)
class Track:
    index: int
    name: str
    start: int
    end: int
    sample_rate: int
    sample_count: int
    channels: int
    codec: int
    loop_start: int
    loop_end: int

    @property
    def duration(self) -> float:
        return self.sample_count / self.sample_rate


class BarsDocument:
    def __init__(self, path: Path):
        self.path = path
        self.was_compressed = path.name.casefold().endswith(".zs")
        self.bars = self._normalized(read_archive(path))
        self.is_bwav = self.bars[:4] == b"BWAV"
        self.is_stream = self.bars[:4] == b"FSTM"
        self.tracks: list[Track] = []
        self.replacements: dict[str, Path] = {}
        self.levels: dict[str, tuple[float, float]] = {}
        seen: set[str] = set()
        if self.is_bwav:
            rate, count, channel_count, codec, loop_start, loop_end = inspect_bwav(self.bars)
            self.tracks.append(Track(0, bwav_name(path.name).removesuffix(".bwav"), 0,
                                     len(self.bars), rate, count, channel_count, codec,
                                     loop_start, loop_end))
            return
        if self.is_stream:
            rate, count, channel_count, codec, loop_start, loop_end = inspect_nintendo_audio(self.bars)
            self.tracks.append(Track(0, bfstm_name(path.name).removesuffix(".bfstm"), 0,
                                     len(self.bars), rate, count, channel_count, -2,
                                     loop_start, loop_end))
            return
        for index, name, start, end in bars_entries(self.bars, require_bwav=False):
            if name in seen:
                raise ValueError(f"Duplicate event name is not supported: {name}")
            seen.add(name)
            if self.bars[start : start + 4] == b"BWAV":
                rate, count, channel_count, codec, loop_start, loop_end = inspect_bwav(
                    self.bars[start:end]
                )
            else:
                # Older BARS contain FWAV/FSTP, which can be decoded for listening
                # but cannot be safely replaced by a Splatoon 3 BWAV encoder.
                rate, count, channel_count, codec, loop_start, loop_end = inspect_nintendo_audio(
                    self.bars[start:end]
                )
                codec = -1
            self.tracks.append(
                Track(
                    index=index,
                    name=name,
                    start=start,
                    end=end,
                    sample_rate=rate,
                    sample_count=count,
                    channels=channel_count,
                    codec=codec,
                    loop_start=loop_start,
                    loop_end=loop_end,
                )
            )

    @staticmethod
    def _normalized(data: bytes) -> bytes:
        if len(data) >= 8 and data[:4] == b"BARS":
            declared = struct.unpack_from("<I", data, 4)[0]
            if declared < len(data) and not any(data[declared:]):
                return data[:declared]
        return data

    def decode_track(self, track: Track) -> tuple[int, list[list[int]]]:
        if track.codec in (-1, -2):
            return self._decode_legacy(self.bars[track.start : track.end])
        rate, _count, channels, _metadata = decode_bwav(self.bars[track.start : track.end])
        return rate, channels

    @staticmethod
    def _decode_legacy(audio: bytes) -> tuple[int, list[list[int]]]:
        import wave

        with tempfile.TemporaryDirectory(prefix="splatoon-legacy-audio-") as folder:
            output = Path(folder) / "sound.wav"
            BarsDocument._render_legacy_wav(audio, output)
            with wave.open(str(output), "rb") as wav:
                if wav.getsampwidth() != 2 or wav.getnchannels() < 1:
                    raise ValueError(f"This older sound is {wav.getnchannels()}-channel "
                                     f"{wav.getsampwidth() * 8}-bit audio, not PCM16")
                rate = wav.getframerate()
                pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
                frames = pcm.reshape(-1, wav.getnchannels())
                if wav.getnchannels() > 2:
                    frames = frames[:, :2]  # Stereo preview of multichannel audio.
                channels = frames.T.tolist()
                return rate, channels

    @staticmethod
    def _render_legacy_wav(audio: bytes, output: Path) -> None:
        _require_native(DECODER_EXE)
        with tempfile.TemporaryDirectory(prefix="splatoon-legacy-audio-input-") as folder:
            source = Path(folder) / "sound.bin"
            source.write_bytes(audio)
            result = subprocess.run(
                [str(DECODER_EXE), str(source), str(output)], capture_output=True,
                text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode:
                raise ValueError(f"This older sound could not be decoded: {result.stderr.strip()}")

    def measure_track(self, track: Track) -> tuple[float, float]:
        if track.name not in self.levels:
            if track.codec in (-1, -2):
                import wave

                with tempfile.TemporaryDirectory(prefix="splatoon-audio-levels-") as folder:
                    output = Path(folder) / "sound.wav"
                    self._render_legacy_wav(self.bars[track.start:track.end], output)
                    with wave.open(str(output), "rb") as wav:
                        peak, squares, total = 0.0, 0.0, 0
                        while chunk := wav.readframes(65536):
                            values = np.frombuffer(chunk, dtype="<i2").astype(np.float64)
                            peak = max(peak, float(np.max(np.abs(values))))
                            squares += float(np.dot(values, values))
                            total += values.size
                        rms = math.sqrt(squares / total) if total else 0.0
                        self.levels[track.name] = (
                            20 * math.log10(peak / 32768) if peak else -math.inf,
                            20 * math.log10(rms / 32768) if rms else -math.inf,
                        )
            else:
                _rate, channels = self.decode_track(track)
                self.levels[track.name] = pcm_levels(channels)
        return self.levels[track.name]

    def extract(self, tracks: list[Track], output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        for track in tracks:
            filename = f"{track.index:03d}_{safe_name(track.name, f'track_{track.index:03d}')}.wav"
            output_path = output_dir / filename
            if track.codec in (-1, -2):
                self._render_legacy_wav(self.bars[track.start:track.end], output_path)
            else:
                rate, channels = self.decode_track(track)
                write_wav(output_path, rate, channels)
        return output_dir

    @staticmethod
    def _compile_encoder() -> None:
        _require_native(ENCODER_EXE)

    @staticmethod
    def _compile_stream_encoder() -> None:
        _require_native(STREAM_ENCODER_EXE)

    def _build_stream(self, output_path: Path, progress) -> dict:
        if output_path.resolve() == self.path.resolve():
            raise ValueError("Choose a different output path; the original file is never overwritten")
        track = self.tracks[0]
        if track.channels not in (1, 2):
            raise ValueError("Replacing BFSTM audio with more than two channels is not supported")
        rebuilt = self.bars
        if track.name in self.replacements:
            self._compile_stream_encoder()
            progress("Converting replacement music...")
            with tempfile.TemporaryDirectory(prefix="splatoon-stream-converter-") as folder:
                temp = Path(folder)
                original = temp / "original.bfstm"
                converted_wav = temp / "replacement.wav"
                result_path = temp / "rebuilt.bfstm"
                original.write_bytes(self.bars)
                source_rate, source_pcm = read_pcm16(self.replacements[track.name])
                pcm = match_channels(source_pcm, track.channels)
                pcm = sinc_resample(pcm, source_rate, track.sample_rate)
                write_pcm16_wav(converted_wav, pcm, track.sample_rate)
                result = subprocess.run(
                    [str(STREAM_ENCODER_EXE), str(original), str(converted_wav), str(result_path)],
                    capture_output=True, text=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if result.returncode:
                    raise RuntimeError(result.stdout + result.stderr)
                rebuilt = result_path.read_bytes()
                rate, count, channels, _codec, loop_start, loop_end = inspect_nintendo_audio(rebuilt)
                if (rate, channels, count) != (track.sample_rate, track.channels, len(pcm)):
                    raise RuntimeError("Saved BFSTM does not match the replacement audio")
                if (loop_end >= 0) != (track.loop_end >= 0):
                    raise RuntimeError("BFSTM loop behavior changed unexpectedly")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = Zstd().compress(rebuilt) if output_path.name.casefold().endswith(".zs") else rebuilt
        output_path.write_bytes(payload)
        if read_archive(output_path) != rebuilt:
            raise RuntimeError("Saved BFSTM failed verification")
        return {
            "source": str(self.path), "output": str(output_path), "source_modified": False,
            "entries_total": 1, "entries_replaced": int(track.name in self.replacements),
            "names_preserved": True, "compression_roundtrip_exact": True,
        }

    @staticmethod
    def _apply_original_loop(replacement: bytes, original: Track, new_count: int) -> bytes:
        if original.loop_end < 0:
            return replacement
        loop_start = round(original.loop_start * new_count / original.sample_count)
        loop_end = (
            new_count
            if original.loop_end == original.sample_count
            else round(original.loop_end * new_count / original.sample_count)
        )
        loop_start = max(0, min(loop_start, new_count - 1))
        loop_end = max(loop_start + 1, min(loop_end, new_count))
        output = bytearray(replacement)
        channel_count = struct.unpack_from("<H", output, 0x0E)[0]
        for channel in range(channel_count):
            header = 0x10 + channel * 0x4C
            struct.pack_into("<ii", output, header + 0x3C, loop_end, loop_start)
        return bytes(output)

    def build(self, output_path: Path, progress) -> dict:
        if self.is_stream:
            return self._build_stream(output_path, progress)
        if any(track.codec == -1 for track in self.tracks):
            raise ValueError("FWAV/FSTP archives are read-only; their replacement format is not supported")
        if output_path.resolve() == self.path.resolve():
            raise ValueError("Choose a different output path; the app never overwrites the source archive")
        if self.replacements:
            self._compile_encoder()
        replacement_blobs: dict[str, bytes] = {}
        audit = []
        by_name = {track.name: track for track in self.tracks}
        with tempfile.TemporaryDirectory(prefix="bars-audio-converter-") as temporary:
            temp = Path(temporary)
            total = max(1, len(self.replacements))
            for position, (event_name, wav_path) in enumerate(self.replacements.items(), start=1):
                progress(f"Converting sound {position} of {total}: {event_name}")
                track = by_name[event_name]
                source_rate, source_pcm = read_pcm16(wav_path)
                pcm = match_channels(source_pcm, track.channels)
                pcm = sinc_resample(pcm, source_rate, track.sample_rate)
                converted_wav = temp / f"{position:04d}.wav"
                encoded_file = temp / f"{position:04d}.gcae"
                write_pcm16_wav(converted_wav, pcm, track.sample_rate)
                result = subprocess.run(
                    [str(ENCODER_EXE), str(converted_wav), str(encoded_file)],
                    capture_output=True,
                    text=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if result.returncode:
                    raise RuntimeError(result.stdout + result.stderr)
                rate, sample_count, encoded_channels = read_gcae(encoded_file)
                replacement = build_adpcm_bwav(rate, sample_count, encoded_channels)
                replacement = self._apply_original_loop(replacement, track, sample_count)
                decode_adpcm_bwav(replacement)
                replacement_blobs[event_name] = replacement
                audit.append(
                    {
                        "event_name": event_name,
                        "source_wav": str(wav_path),
                        "target_sample_rate": rate,
                        "target_channels": len(encoded_channels),
                        "target_samples": sample_count,
                        "loop_preserved": track.loop_end >= 0,
                    }
                )

        progress("Putting the sounds back into the file...")
        if self.is_bwav:
            rebuilt = replacement_blobs.get(self.tracks[0].name, self.bars)
            inspect_bwav(rebuilt)
            if replacement_blobs:
                decode_adpcm_bwav(rebuilt)
        else:
            rebuilt = rebuild_bars(self.bars, replacement_blobs)
            # Structural and codec validation before writing anything.
            verified_records = list(bars_entries(rebuilt))
            if [record[1] for record in verified_records] != [track.name for track in self.tracks]:
                raise RuntimeError("BARS event-name verification failed")
            for _, name, start, end in verified_records:
                if name in replacement_blobs:
                    decode_adpcm_bwav(rebuilt[start:end])

        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.name.casefold().endswith(".zs"):
            progress("Compressing the file...")
            payload = Zstd().compress(rebuilt)
        else:
            payload = rebuilt
        output_path.write_bytes(payload)

        progress("Checking the saved file...")
        saved = self._normalized(read_archive(output_path))
        if saved != rebuilt:
            raise RuntimeError("Saved archive failed exact decompression verification")
        return {
            "source": str(self.path),
            "output": str(output_path),
            "source_modified": False,
            "entries_total": len(self.tracks),
            "entries_replaced": len(replacement_blobs),
            "names_preserved": True,
            "compression_roundtrip_exact": True,
            "replacements": audit,
        }
