"""Verify the actual portable Windows executable opens generated audio."""
from pathlib import Path
import argparse
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from fixtures import bars


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    output = ROOT / "test-output"
    output.mkdir(exist_ok=True)
    sound = output / "Preview_Sounds.bars"
    sound.write_bytes(bars(("Preview_Chime", "Preview_Confirm", "Preview_Loop",
                            "Preview_Notification", "Preview_Scroll", "Preview_Start")))
    picture = output / "packaged.png"
    executable = args.dist_dir.resolve() / "Splatoon Audio Converter/Splatoon Audio Converter.exe"
    result = subprocess.run([str(executable), str(sound), "--snapshot", str(picture)],
                            capture_output=True, text=True, timeout=45,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        message = (result.stdout + result.stderr).replace(str(Path.home()), "[user]")
        raise RuntimeError(f"Portable application exited with {result.returncode}: {message[-3000:]}")
    if not picture.is_file() or not picture.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("Portable application did not produce its test rendering.")
    print("PASS: portable EXE opened BARS audio, decoded a waveform and rendered its window.")


if __name__ == "__main__":
    main()
