# Changelog

## 2.2.0

- Settings button with Beige (default), Navy Blue, Brown, Purple and Green themes.
- All themes include the title bar and normal window controls.
- Appearance choice is remembered between launches, with no audio paths saved.
- Preview volume now supports 0–300%.
- Replaced boosted-WAV regeneration with live, click-ramped PCM gain, preventing
  volume changes from stopping/reloading the track or interrupting the interface.
- Removed the requested replacement-format, loop-behavior and export-note texts.
- Added continuous-playback, rapid-volume, saved-theme and window-frame tests.

## 2.1.0

- Purple standalone desktop interface with rounded panels.
- Optional user-supplied NinDev-Treasure interface font.
- Visible Check for Updates button; removed File/Playback/Help menus.
- Circular-arrow replay button immediately starts the selected track again.
- Preview volume defaults to 100%, with real temporary-copy amplification to 200%.
- Simplified four-step quick guide.
- BARS, BWAV and BFSTM opening, preview, extraction and replacement.
- Original files remain unchanged; no extraction manifest/JSON files.
- Filename suffixes are normalized so `.bars.zs` is added only once.
- GitHub-tested builds, portable downloads, source ZIPs and checksums.
- Release scans check application code and bundled files for personal build paths.
