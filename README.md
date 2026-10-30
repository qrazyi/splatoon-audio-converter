# Splatoon Audio Converter

Extract WAVs, replace audio tracks or preview sounds.

A standalone desktop app with seven glass-inspired themes, rounded controls and a
three-column audio workbench. The visual arrangement was inspired by
[HoianViewer](https://github.com/nvnprogram/HoianViewer), but its UI code, fonts,
artwork and game assets have not been copied into this project.

[Download the latest release](https://github.com/qrazyi/splatoon-audio-converter/releases/latest)
· [Report an issue](https://github.com/qrazyi/splatoon-audio-converter/issues)

![Audio workbench](docs/preview.png)

The preview shows the default Brown theme and an optional user-supplied font. Public downloads use the system
font unless you supply your own; Nintendo font software is not redistributed.

## Windows download

Extract the **complete portable folder**, then run **Splatoon Audio Converter.exe**.
Keep `_internal` beside the EXE; it contains the audio, playback and UI libraries.
There is no installer and the title contains no version number.

Windows 10/11 x64 is the supported build. Python, FFmpeg applications, Switch
Toolbox, a game ROMFS and a separate media player are not required. The small
Nintendo audio helpers use Windows .NET Framework 4.x; install Microsoft's .NET
Framework 4.8 runtime if a Windows installation does not already provide it.
Qt playback libraries, NumPy, Zstandard and VGAudio are included in the download.

The UI and pure Python engine can be developed on other systems, but the bundled
Nintendo stream/conversion helpers are currently Windows-only. This is **not**
advertised as a fully supported macOS/Linux release.

## Work with audio

1. Open an audio file
2. Select a track to listen to
3. Choose a replacement .wav file
4. Save as a new file.

Your original files are not affected.

Supported files: `.bars`, `.bars.zs`, `.bwav`, `.bwav.zs`, `.bfstm`, `.bfstm.zs`.
Drag and drop also works. To preview audio, click a track's play icon or the large
play/pause button. The circular-arrow button immediately replays from the start,
even when paused. Click the waveform to seek.

Preview volume defaults to 100% and supports 0–300% (up to +9.54 dB). Gain changes
are applied to small audio buffers in real time, without stopping the track,
reopening files, rewriting WAVs or refreshing the waveform. Short gain ramps
reduce clicks. Loud sounds may clip. This does not
change original files, extracted WAVs or saved replacements. Audio feeding runs
on a dedicated high-priority thread with a precise timer and a 200 ms buffer,
independent of UI focus, painting and covered/hidden windows.

### Appearance settings

Open **Themes** to choose **Beige**, **Blue**, **Brown**, **Green**, **Orange**,
**Purple** or **Yellow**, sorted alphabetically. Brown is the default for a fresh
install. Your choice is remembered
between launches. It changes the whole interface, including the title bar,
window controls, waveform, menus and buttons.

The interface uses translucent layered panels, reflective rims and pill-shaped
controls inspired by glass materials. This is an original Qt implementation,
not Apple's native Liquid Glass framework. Previously saved Navy Blue
preferences are automatically treated as Blue; other explicit choices are kept.

The themed title bar supports dragging and double-clicking to maximize/restore,
with minimize, maximize/restore and close controls. Window borders can be dragged
to resize. Appearance settings contain only the theme name, never audio paths,
and are stored in your account's application settings, not beside game files.

For replacements, use a **mono/stereo 16-bit PCM WAV**. The Original sound /
Replacement WAV selector lets you compare them. Sample rate and channel count
are matched to the original when saving. BARS exports as `.bars.zs`; standalone
music keeps its BWAV/BFSTM format and original compression choice.

### Optional custom font

If its terms permit your use, put your own `NinDev-Treasure_00.ttf` in the `fonts`
folder beside the EXE, then restart. The font is optional and is not uploaded or
included in public releases. See [fonts/README.md](fonts/README.md).

### Keyboard shortcuts

- Ctrl+O: open audio
- Space: play/pause
- Ctrl+R: immediately replay
- Ctrl+Shift+S: save as a new game audio file
- F1: about and version information

### File handling

The extension is added only once. The source file cannot be overwritten.
Event names and metadata are retained. Loop behavior is preserved automatically;
the original loop's relative position is adjusted to the replacement's length.
There is no editable "loop system" to configure accidentally.

Extraction produces WAVs only: no manifest, audit JSON or sidecar configuration.
Extraction uses the original track, not an assigned replacement WAV.

Older BARS containing FWAV/FSTP tracks are read-only. FSTP is a short prefetch:
its header can describe the whole song, but only the stored audio can be extracted.
Replacement of audio with more than two channels is not supported.

## Downloads and source builds

Configured project: https://github.com/qrazyi/splatoon-audio-converter

- The application contains no GitHub button, updater or network requests.
  Download and extract a newer portable release manually when you want one.
- `.github/workflows/build.yml` tests, builds and privacy-checks the Windows app.
  Normal pushes/PRs produce downloadable build artifacts. A pushed `v*` tag
  additionally publishes a GitHub Release with the portable ZIP and checksum.

Before a release, review the included third-party notices and
bump both the package version in
`pyproject.toml` and `src/splatoon_audio_converter/__init__.py`.

## Develop and build

Use Python 3.12 on Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install . pyinstaller
python scripts/build_native.py
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -p "test_*.py" -v
python tests/smoke_ui.py
python tests/smoke_playback.py
python launch.py
python -m PyInstaller --noconfirm "Splatoon Audio Converter.spec"
python scripts/smoke_frozen.py
python scripts/check_privacy.py dist
python scripts/package_release.py
```

The build uses the included MIT-licensed `VGAudio.dll`; the helper source code is
in `native-src/`. Rebuilding helpers needs the Windows .NET Framework C# compiler.
The `make_test_stream` helper and generated test sounds are development fixtures
only and are not bundled with the app.

The packaging script also creates a clean source ZIP, excluding local build logs,
caches and generated test output. Use that ZIP when sharing source outside Git.
Private development fonts in `local-assets` are excluded from Git and source ZIPs.
The build can bundle a local font for personal use, but never upload such a build
unless you have obtained permission to redistribute that font.

## Privacy and redistribution

No author machine paths are hardcoded in the application. File labels and
activity messages show filenames, not the full local path. No telemetry is
implemented; audio is never uploaded. The app operates offline and makes no
update checks or other network requests. Temporary previews are cleaned on close.

Release checking scans normal files and decompressed frozen Python code for
personal user-profile paths, and rejects all profile paths in application code.
Known third-party CI/build paths and documentation examples are reported
separately; signed upstream libraries are not modified to erase that metadata.
Do not package the old converter directory, test
output, local configuration, a ROMFS, or example audio from the game.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Keep all third-party license
files with the portable folder when sharing it.

The project's own code is [MIT licensed](LICENSE). This project is not affiliated
with or endorsed by Nintendo.
