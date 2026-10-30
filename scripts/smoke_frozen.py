"""Verify the actual portable Windows executable opens generated audio."""
from pathlib import Path
import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
import zipfile

from PySide6.QtCore import QCoreApplication
from PySide6.QtMultimedia import QMediaDevices

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from fixtures import bars, pcm_bwav, replacement_wav
from splatoon_audio_converter.core import Zstd


def verify(executable, output, cwd):
    supplied = ROOT / "src/splatoon_audio_converter/assets/fonts/NinDev-Treasure_00.ttf"
    bundled = executable.parent / "_internal/splatoon_audio_converter/assets/fonts/NinDev-Treasure_00.ttf"
    if not bundled.is_file() or hashlib.sha256(bundled.read_bytes()).digest() != hashlib.sha256(supplied.read_bytes()).digest():
        raise RuntimeError("The supplied interface font is missing or has changed in the portable app.")
    app = QCoreApplication.instance() or QCoreApplication([])
    playback = not QMediaDevices.defaultAudioOutput().isNull()
    cases = []
    sound = output / "Preview_Sounds.bars"
    sound.write_bytes(bars(("Preview_Chime", "Preview_Confirm", "Preview_Loop",
                            "Preview_Notification", "Preview_Scroll", "Preview_Start")))
    cases.append((sound, "packaged"))
    compressed = sound.with_name("Preview_Sounds.bars.zs")
    compressed.write_bytes(Zstd().compress(sound.read_bytes()))
    cases.append((compressed, "packaged-bars-zs"))
    bwav = output / "Preview_Sound.bwav"
    bwav.write_bytes(pcm_bwav(seconds=.4))
    cases.append((bwav, "packaged-bwav"))
    fixture_tool = ROOT / "test-output/make_test_stream.exe"
    for channels in (1, 2, 4, 10):
        wav = output / f"Generated_{channels}.wav"
        source = output / f"Generated_{channels}.bfstm"
        replacement_wav(wav, seconds=.4, rate=48000, channels=channels)
        subprocess.run([str(fixture_tool), str(wav), str(source)], check=True, capture_output=True)
        cases.append((source, f"packaged-bfstm-{channels}"))
        if channels == 10:
            compressed = source.with_suffix(".bfstm.zs")
            compressed.write_bytes(Zstd().compress(source.read_bytes()))
            cases.append((compressed, "packaged-bfstm-zs"))
    env = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH",
                 "QT_QPA_PLATFORM", "QML2_IMPORT_PATH", "SAC_INCLUDE_PRIVATE_FONT"):
        env.pop(name, None)
    windows = Path(env.get("WINDIR", "C:/Windows"))
    env["PATH"] = os.pathsep.join(str(windows / part) for part in ("System32", "."))
    before = {p.relative_to(executable.parent) for p in executable.parent.rglob("*") if p.is_file()}
    for sound, name in cases:
        picture = output / f"{name}.png"
        command = [str(executable), str(sound), "--snapshot", str(picture)]
        if playback:
            command.append("--test-playback")
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=45,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode:
            message = (result.stdout + result.stderr).replace(str(Path.home()), "[user]")
            raise RuntimeError(f"Portable app failed {name} ({result.returncode}): {message[-3000:]}")
        if not picture.is_file() or not picture.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError(f"Portable app did not render {name}.")
        print(f"PASS: portable EXE decoded/rendered {sound.suffixes}; muted playback {'passed' if playback else 'skipped (no output device)'}. {name}")
    after = {p.relative_to(executable.parent) for p in executable.parent.rglob("*") if p.is_file()}
    if after != before:
        raise RuntimeError("Portable app wrote files inside its distribution folder.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--zip", type=Path, help="Test a fresh extraction of the final public ZIP")
    args = parser.parse_args()
    output = ROOT / "test-output"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="portable-audio-check-") as temporary:
        cwd = Path(temporary)
        distribution = args.dist_dir.resolve()
        if args.zip:
            with zipfile.ZipFile(args.zip) as archive:
                for name in archive.namelist():
                    if not (cwd / name).resolve().is_relative_to(cwd.resolve()):
                        raise ValueError("ZIP contains an unsafe filename")
                archive.extractall(cwd)
            distribution = cwd
        verify(distribution / "Splatoon Audio Converter/Splatoon Audio Converter.exe", output, cwd)


if __name__ == "__main__":
    main()
