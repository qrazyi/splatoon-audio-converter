"""Original, procedurally generated sounds for tests. No game assets."""
import struct
import wave
from pathlib import Path

import numpy as np


def pcm_bwav(seconds=.32, rate=32000, frequency=440, loop=False):
    count = max(1, round(seconds * rate))
    times = np.arange(count) / rate
    envelope = np.minimum(1, times * 25) * np.maximum(0, 1 - times / seconds)
    pcm = np.rint(np.sin(times * frequency * 2 * np.pi) * envelope * 13500).astype("<i2")
    output = bytearray(0x80 + pcm.nbytes)
    struct.pack_into("<4sHHIHH", output, 0, b"BWAV", 0xFEFF, 1, 0, 0, 1)
    struct.pack_into("<HHIII", output, 0x10, 0, 2, rate, count, count)
    struct.pack_into("<II", output, 0x40, 0x80, 0x80)
    struct.pack_into("<Iii", output, 0x48, 1, count if loop else -1, 0)
    output[0x80:] = pcm.tobytes()
    return bytes(output)


def bars(names=("Preview_Chime", "Preview_Confirm", "Preview_Loop")):
    size = 0x10 + len(names) * 12
    output = bytearray(size)
    output[:4] = b"BARS"
    struct.pack_into("<I", output, 0x0C, len(names))
    metadata = []
    for name in names:
        metadata.append(len(output))
        header = bytearray(0x28)
        header[:4] = b"AMTA"
        struct.pack_into("<I", header, 0x24, 4)
        output += header + name.encode() + b"\0"
    for i, name in enumerate(names):
        output.extend(bytes((-len(output)) % 64))
        audio = len(output)
        output += pcm_bwav(.32 + i * .13, frequency=440 + i * 110, loop=i == 2)
        struct.pack_into("<II", output, 0x10 + len(names) * 4 + i * 8, metadata[i], audio)
    struct.pack_into("<I", output, 4, len(output))
    return bytes(output)


def replacement_wav(path: Path, seconds=.5, rate=44100, channels=1):
    pcm = np.rint(np.sin(np.arange(round(seconds * rate)) / rate * 660 * 2 * np.pi) * 9000).astype("<i2")
    pcm = np.repeat(pcm[:, None], channels, axis=1)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(pcm.tobytes())
