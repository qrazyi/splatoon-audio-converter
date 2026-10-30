"""Temporary WAV previews and waveform data. Never writes next to input files."""
from __future__ import annotations

import math
import wave
import hashlib
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from .core import BarsDocument, Track, write_wav


@dataclass
class Preview:
    path: Path
    peaks: np.ndarray
    duration: float
    peak_db: float
    average_db: float
    replacement: bool
    playback_path: Path | None = None
    gain: int = 100


def with_volume(preview: Preview, cache: Path, volume: int) -> Preview:
    """Boost temporary playback audio only; originals/exports are never changed."""
    gain = max(100, min(200, volume))
    if gain == 100:
        return replace(preview, playback_path=preview.path, gain=gain)
    stat = preview.path.stat()
    key = f"{preview.path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}|{gain}"
    name = hashlib.sha256(key.encode()).hexdigest()[:24]
    target = cache / f"volume-{name}.wav"
    if not target.is_file():
        cache.mkdir(parents=True, exist_ok=True)
        with wave.open(str(preview.path), "rb") as source, wave.open(str(target), "wb") as output:
            if source.getsampwidth() != 2 or source.getcomptype() != "NONE":
                raise ValueError("Preview boost requires a 16-bit PCM WAV.")
            output.setparams(source.getparams())
            while block := source.readframes(65536):
                pcm = np.frombuffer(block, dtype="<i2").astype(np.float64)
                pcm = np.clip(np.rint(pcm * gain / 100), -32768, 32767).astype("<i2")
                output.writeframesraw(pcm.tobytes())
    return replace(preview, playback_path=target, gain=gain)


def waveform(path: Path, bins: int = 1200) -> tuple[np.ndarray, float, float, float]:
    # Read in blocks: a full BFSTM song need not be duplicated in memory here.
    with wave.open(str(path), "rb") as source:
        if source.getsampwidth() != 2 or source.getcomptype() != "NONE":
            raise ValueError("Preview requires a 16-bit PCM WAV file.")
        frames, channels, rate = source.getnframes(), source.getnchannels(), source.getframerate()
        if frames == 0 or channels == 0 or rate == 0:
            raise ValueError("This WAV file has no playable samples.")
        bins = min(bins, frames)
        peaks = np.zeros(bins, dtype=np.float32)
        peak, squares, count, frame_offset = 0.0, 0.0, 0, 0
        while chunk := source.readframes(65536):
            pcm = np.frombuffer(chunk, dtype="<i2").reshape(-1, channels).astype(np.float64)
            magnitudes = np.max(np.abs(pcm), axis=1)
            indices = np.minimum((np.arange(len(pcm)) + frame_offset) * bins // frames, bins - 1)
            np.maximum.at(peaks, indices, magnitudes / 32768.0)
            peak = max(peak, float(magnitudes.max()))
            squares += float(np.square(pcm).sum())
            count += pcm.size
            frame_offset += len(pcm)
        rms = math.sqrt(squares / count)
    return (peaks, frames / rate,
            20 * math.log10(peak / 32768) if peak else -math.inf,
            20 * math.log10(rms / 32768) if rms else -math.inf)


def prepare(document: BarsDocument, track: Track, cache: Path, replacement: bool, volume: int = 100) -> Preview:
    replacement_path = document.replacements.get(track.name) if replacement else None
    if replacement_path:
        path = replacement_path
    else:
        path = cache / f"track-{track.index:05d}.wav"
        if not path.is_file():
            if track.codec in (-1, -2):
                document._render_legacy_wav(document.bars[track.start:track.end], path)
            else:
                rate, channels = document.decode_track(track)
                write_wav(path, rate, channels)
    return with_volume(Preview(path, *waveform(path), bool(replacement_path)), cache, volume)
