# Optional interface font

The supplied Nintendo font is not licensed for redistribution by this project.
It is deliberately excluded from Git and public releases.

If you have permission to use it, put your own `NinDev-Treasure_00.ttf` here
(the `fonts` folder beside the application executable), then restart the app.
Otherwise the app uses the system font. Original font paths are never stored.

For private development, `local-assets/NinDev-Treasure_00.ttf` is also detected.
That directory is ignored by Git and is excluded from the clean source ZIP.
Local builds can bundle that private copy; do not upload those builds publicly
unless you have obtained the required redistribution permission.
