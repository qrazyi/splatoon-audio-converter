"""Rebuild the small Windows codec helpers from the included C# sources."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "src/splatoon_audio_converter/native"


def main():
    compiler = Path(os.environ.get("WINDIR", "C:/Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    if not compiler.is_file():
        raise SystemExit("Windows .NET Framework C# compiler is required to rebuild the helpers.")
    library = OUTPUT / "VGAudio.dll"
    if not library.is_file():
        raise SystemExit("Restore the MIT-licensed native/VGAudio.dll dependency before building.")
    for name in ("gcadpcm_encode", "nintendo_audio_decode", "nintendo_stream_encode"):
        subprocess.run([str(compiler), "/nologo", "/optimize+", "/debug-", "/platform:x64",
                        f"/reference:{library}", f"/out:{OUTPUT / (name + '.exe')}",
                        str(ROOT / "native-src" / (name + ".cs"))], check=True)
        print("Built", name + ".exe")
    test_output = ROOT / "test-output"
    test_output.mkdir(exist_ok=True)
    subprocess.run([str(compiler), "/nologo", "/optimize+", "/debug-", "/platform:x64",
                    f"/reference:{library}", f"/out:{test_output / 'make_test_stream.exe'}",
                    str(ROOT / "native-src/make_test_stream.cs")], check=True)
    shutil.copy2(library, test_output / "VGAudio.dll")


if __name__ == "__main__":
    main()
