# Interface font

The supplied NinDev-Treasure_00.ttf font is now bundled with the app in
`src/splatoon_audio_converter/assets/fonts` and included in portable releases.
Its original copyright/terms remain unchanged; the project's MIT code license
does not relicense the font.

No separate font installation is needed. Original font paths are never stored.
The app falls back to the system font if it cannot load the supplied font.

Other private development files in `local-assets` remain ignored by Git and
excluded from release ZIPs.
