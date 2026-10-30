"""Bundle the verified portable folder with filename-only release checksums."""
import hashlib
import argparse
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUNDLED_FONT = "src/splatoon_audio_converter/assets/fonts/NinDev-Treasure_00.ttf"
RUNTIME_FONT = "_internal/splatoon_audio_converter/assets/fonts/NinDev-Treasure_00.ttf"


def release_files(folder):
    """Keep only the executable and runtime at the top of the download."""
    root_files = {"Splatoon Audio Converter.exe"}
    forbidden_parts = {"local-assets", "test-output", "__pycache__", ".git", ".venv"}
    forbidden_suffixes = {".ttf", ".otf", ".pdb", ".log", ".ini", ".cfg", ".json",
                          ".wav", ".bars", ".bwav", ".bfstm", ".zs"}
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(folder)
        supplied_font = (relative.as_posix() == RUNTIME_FONT and
                         hashlib.sha256(path.read_bytes()).digest() ==
                         hashlib.sha256((ROOT / BUNDLED_FONT).read_bytes()).digest())
        # Old development guides are not part of the end-user download.
        if relative.as_posix() in ("README.md", "fonts/README.md", "START HERE.txt", "LICENSE", "THIRD_PARTY_NOTICES.md") or path.name == ".gitkeep":
            continue
        if (set(relative.parts) & forbidden_parts or (path.suffix.lower() in forbidden_suffixes and not supplied_font)
                or (relative.parts[0] != "_internal" and relative.as_posix() not in root_files)):
            raise ValueError(f"Non-release file found in portable folder: {relative.as_posix()}")
        yield path


def source_files():
    for name in ("launch.py", "pyproject.toml", "Splatoon Audio Converter.spec",
                 "README.md", "QUICK_START.txt", "THIRD_PARTY_NOTICES.md", "LICENSE", "CHANGELOG.md", ".gitignore"):
        yield ROOT / name
    for name in ("src", "tests", "scripts", "native-src", "licenses", ".github", "fonts", "docs"):
        for path in sorted((ROOT / name).rglob("*")):
            if (path.is_file() and "__pycache__" not in path.parts and
                    (path.suffix not in (".pyc", ".pyo", ".ttf", ".otf") or path.relative_to(ROOT).as_posix() == BUNDLED_FONT)):
                yield path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    distribution = args.dist_dir.resolve()
    folder = distribution / "Splatoon Audio Converter"
    if not (folder / "Splatoon Audio Converter.exe").is_file():
        raise SystemExit("Build and verify the portable app before packaging it.")
    notices = folder / "_internal/licenses/application"
    notices.mkdir(parents=True, exist_ok=True)
    for name in ("THIRD_PARTY_NOTICES.md", "LICENSE"):
        shutil.copy2(ROOT / name, notices / name)
    files = list(release_files(folder))  # Validate before creating a public ZIP.
    target = distribution / "Splatoon-Audio-Converter-win-x64.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files:
            archive.write(path, Path(folder.name) / path.relative_to(folder))
    source = distribution / "Splatoon-Audio-Converter-source.zip"
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in source_files():
            archive.write(path, Path("Splatoon Audio Converter") / path.relative_to(ROOT))
    checksums = "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in (target, source))
    (target.parent / "SHA256SUMS.txt").write_text(checksums, encoding="utf-8")
    print(f"Created {target.name} ({target.stat().st_size / 1024**2:.1f} MB)")
    print(f"Created {source.name}; development output, caches and local build logs excluded.")


if __name__ == "__main__":
    main()
