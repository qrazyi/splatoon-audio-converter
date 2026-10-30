"""Run from source after installing the project dependencies."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from splatoon_audio_converter.ui import main

if __name__ == "__main__":
    main()
