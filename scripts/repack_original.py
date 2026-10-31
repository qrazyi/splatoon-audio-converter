"""Create a smaller copy of an existing working v2.4.2 portable folder.

Never edit the baseline. The executable, application code, UI, font, audio
helpers and retained runtime files are copied byte-for-byte and verified.
"""
import argparse
import hashlib
from pathlib import Path
import shutil

from runtime_layout import omit_runtime


def digest(path):
    return hashlib.sha256(path.read_bytes()).digest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    source, destination = args.source.resolve(), args.destination.resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise SystemExit("Use separate, non-nested source and destination folders.")
    if destination.exists():
        raise SystemExit("Destination already exists. Choose a new folder; nothing was overwritten.")
    if not (source / "Splatoon Audio Converter.exe").is_file():
        raise SystemExit("Choose the working portable application folder.")
    original = {path.relative_to(source): digest(path) for path in source.rglob("*") if path.is_file()}
    removed = 0
    for relative, before in original.items():
        path = source / relative
        if omit_runtime(relative):
            removed += path.stat().st_size
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        if digest(target) != before:
            raise RuntimeError("A retained file changed during copying.")
    if any(digest(source / relative) != before for relative, before in original.items()):
        raise RuntimeError("The baseline changed during copying.")
    total = sum(path.stat().st_size for path in destination.rglob("*") if path.is_file())
    print(f"PASS: baseline unchanged; every retained file is byte-identical.")
    print(f"Omitted {removed / 1024**2:.1f} MiB of unused optional runtime components.")
    print(f"Portable folder: {total / 1024**2:.1f} MiB. UI, font and audio engine unchanged.")


if __name__ == "__main__":
    main()
