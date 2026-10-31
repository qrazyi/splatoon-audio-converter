# Third-party notices

## Version 3 lightweight app

The native version in `native-app/` ships VGAudio (MIT), Zstandard (BSD) and the
separately supplied interface font. Its required notices are under
`_internal/licenses`; Windows supplies .NET Framework, Windows Forms and WinMM.
It does not ship Python, Qt, NumPy or FFmpeg. See `native-app/licenses/NOTICES.txt`.

## Archived version 2 implementation

The following component list describes the earlier Python/Qt build, whose source
is retained here for reference. Those runtime components are not part of v3.

The desktop interface is an original implementation. Its custom styling and
three-panel arrangement were inspired by HoianViewer by nvnprogram:
https://github.com/nvnprogram/HoianViewer

No HoianViewer source code, fonts, textures, logos, or game assets are included.
No game audio, models or effects are distributed. Test sounds are generated mathematically.
The NinDev-Treasure_00.ttf interface font was supplied by the project owner and
is bundled as requested. Its original copyright and terms remain with its owner;
the project's MIT license covers the application code, not this font. Inclusion
does not establish or change the font's redistribution rights.

Runtime components:

- **Python runtime** — Python Software Foundation and contributors.
  Its license and included historical/third-party notices are shipped in
  `licenses/Python/LICENSE.txt` inside the runtime folder.
  Source: https://github.com/python/cpython
- **Qt for Python / PySide6, Shiboken and Qt** — The Qt Company and contributors.
  LGPLv3/GPLv3/commercial licensing as applicable to the selected modules.
  Source: https://code.qt.io/pyside/pyside-setup.git
  Qt source: https://code.qt.io/qt/qt5.git
  Terms: https://doc.qt.io/qtforpython-6/licenses.html
  This application uses dynamically loaded Qt libraries. They are shipped as
  separate files in the portable folder, not statically linked. Users may
  replace the applicable libraries with compatible modified builds.
- **VGAudio** — MIT license; see `licenses/VGAudio-MIT.txt`.
  Source: https://github.com/Thealexbarney/VGAudio
  The three small helper programs are built from the included `native-src/`
  files. Windows .NET Framework is used to run them.
- **NumPy** — BSD-3-Clause and included third-party notices.
  Source: https://github.com/numpy/numpy
- **python-zstandard / Zstandard** — BSD/MIT licenses as described by upstream.
  Source: https://github.com/indygreg/python-zstandard
  Source: https://github.com/facebook/zstd
- **FFmpeg libraries supplied with Qt Multimedia** — see the Qt package's
  FFmpeg notices and applicable LGPL license. Source: https://ffmpeg.org/
- **charset-normalizer**, when collected by the build — MIT license; its
  notice is included in the runtime licenses folder.
  Source: https://github.com/jawah/charset_normalizer

The build script collects the installed packages' license/notice files into the
portable download. Do not remove those files when redistributing the app.
The project's own code is MIT-licensed; see LICENSE. Dependency licenses remain
independent and are not replaced by that license.
