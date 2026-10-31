# Interface font

The supplied NinDev-Treasure_00.ttf font is stored in
`src/splatoon_audio_converter/assets/fonts`. Version 3 embeds it in the EXE for
normal themes. Legacy uses only the Windows system font. Earlier v2 portable
builds included it as a separate runtime asset.
Its original copyright/terms remain unchanged; the project's MIT code license
does not relicense the font.

No separate font installation is needed. Original font paths are never stored.
The app falls back to the system font if it cannot load the supplied font.

Other private development files in `local-assets` remain ignored by Git and
excluded from release ZIPs.
