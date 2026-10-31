# Changelog

## 3.0.0

- Rebuilt the main Windows app with lightweight native controls, GDI+ waveform
  drawing and WinMM audio. Removed the bundled Python/Qt/NumPy/FFmpeg runtimes.
  The complete portable folder is about 1 MB, with a strict 20 MiB packaging cap.
- Added Legacy: black background, white text, Windows system font, no gradients,
  flat controls and no Quick Guide. Audio features remain available in every theme.
- Kept Aqua, Beige, Dark Aero, Dorfic (default) and Eco with the supplied font.
- Retained raw/compressed BARS, BWAV and BFSTM, waveform seeking, 300% live gain,
  immediate restart, extraction, replacements, loops and original-file protection.
- Fixed mixed archives with short prefetches: stored samples preview/extract while
  their untouched payloads are retained when other editable tracks are replaced.
- Replaced custom window chrome with native maximize/resize controls. Playback
  runs independently of UI painting/focus and volume changes do not reload audio.
- Public packages contain no settings, logs, game samples, debug symbols or
  personal profile paths. Only the app, small codec and essential notices ship.
- New procedural tests and fresh-ZIP checks cover all extensions, multichannel
  music, replacement/loop metadata, playback and Legacy/theme switching.

## 2.4.2

- Restored the supplied interface font in the app, source builds and portable ZIP.
- Packaging permits only that exact font at its runtime asset location; other
  private fonts, settings, logs, personal paths and game audio remain excluded.
- Release tests now fail if the supplied font is missing from the download.
- Removed START HERE and top-level license/notice files from the portable ZIP;
  required notices now live under `_internal/licenses/application`.
- Kept the BFSTM playback fix and all existing audio/theme fixes.

## 2.4.1

- Fixed BFSTM playback on ordinary stereo devices: multichannel Nintendo music
  previews its first stereo layer instead of requesting unsupported 4–32-channel
  hardware output. The waveform follows the audible pair; extraction is unchanged.
- Added floating-point PCM output for devices without 16-bit output support.
- Tested raw/compressed BFSTM, multichannel decoding, playback, extraction and
  stereo replacement, alongside the existing BARS/BWAV checks.
- Public builds omit private fonts even when present on the build machine.
- Downloads contain one short start guide plus essential license notices, not
  development READMEs, personal settings, logs, test sounds or local files.
- Added public-package rejection checks and fresh-ZIP executable tests with
  development Python/Qt paths removed from the environment.

## 2.4.0

- Reverted Liquid Glass styling to the original opaque rounded-panel interface.
- Replaced themes with Aqua, Beige, Dark Aero, Dorfic (default) and Eco, sorted
  alphabetically, using the requested exact two-color gradient endpoints.
- Rounded the theme dropdown's native popup shape as well as its menu items.
- Removed theme preferences fall back to Dorfic; saved Beige remains available.
- Kept the offline UI, 300% volume, background-audio worker and fullscreen fixes.

## 2.3.0

- Glass-inspired translucent panels, reflective edges and pill-shaped controls.
- Renamed Settings to Themes and sorted all choices alphabetically: Beige,
  Blue, Brown (new default), Green, Orange, Purple and Yellow.
- Migrated old Navy Blue preferences to Blue without discarding other choices.
- Removed the Audio Levels panel, GitHub button and the complete update checker.
- Corrected resize-cursor inheritance when maximizing, entering fullscreen,
  moving into controls or leaving the window.
- Moved audio feeding off the GUI thread, with a high-priority precise-timer
  worker and 200 ms buffering to prevent covered-window playback starvation.
- Added real-device hidden-window and blocked-UI playback regression checks.

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
