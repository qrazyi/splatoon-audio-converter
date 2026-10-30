"""Check release files and frozen Python code for personal build-machine paths."""
from __future__ import annotations

import argparse
import marshal
import re
from pathlib import Path

PROFILE = re.compile(r"(?:[a-z]:/+users/|/(?:users|home)/)([^/\s\x00\"']{2,})", re.I)
# These are observed upstream Qt/Python/NumPy build roots or documentation
# examples, not this application's author. Never allow them in our own code.
UPSTREAM_EXAMPLES = {"qt", "administrator", "runneradmin", "guido", "guido.foobar.txt", "user", "barney"}


def profile_names(data):
    names = set()
    for value in (data.decode("utf-8", errors="ignore"),
                  data.decode("utf-16-le", errors="ignore"),
                  data[1:].decode("utf-16-le", errors="ignore")):
        value = re.sub(r"/+", "/", value.replace("\\", "/"))
        names.update(match.group(1).casefold() for match in PROFILE.finditer(value))
    return names


def matches(data, *, own_code=False, ci=False):
    names = profile_names(data)
    if own_code:
        return bool(names)
    personal = Path.home().name.casefold()
    # GitHub's generic build account also occurs in official NumPy wheels.
    personal_hit = personal in names and not (ci and personal == "runneradmin")
    return personal_hit or bool(names - UPSTREAM_EXAMPLES)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("--ci", action="store_true", help="Allow upstream runneradmin build metadata in third-party libraries")
    args = parser.parse_args()
    failures = []
    upstream_files = 0
    for path in args.target.rglob("*"):
        if not path.is_file():
            continue
        raw = path.read_bytes()
        own = path.suffix.lower() in (".py", ".pyw")
        if matches(raw, own_code=own, ci=args.ci):
            failures.append(path.relative_to(args.target).as_posix())
        elif profile_names(raw):
            upstream_files += 1
        if path.suffix.lower() == ".exe" and path.name == "Splatoon Audio Converter.exe":
            from PyInstaller.archive.readers import CArchiveReader
            reader = CArchiveReader(str(path))
            for name, entry in reader.toc.items():
                if entry[-1] == "z":
                    archive = reader.open_embedded_archive(name)
                    for module in archive.toc:
                        code = archive.extract(module)
                        if code is not None and matches(marshal.dumps(code), own_code=module.startswith("splatoon_audio_converter"), ci=args.ci):
                            failures.append(f"frozen module: {module}")
                elif entry[-1] in ("s", "m", "M") and matches(reader.extract(name), own_code=True, ci=args.ci):
                    failures.append(f"frozen script: {name}")
    if failures:
        raise SystemExit("Local user paths found in: " + ", ".join(failures))
    print("PASS: no personal profile paths found; application code has no user-profile literals.")
    if upstream_files:
        print(f"Note: {upstream_files} third-party files contain known upstream CI/build or example paths. Those are not author paths.")


if __name__ == "__main__":
    main()
