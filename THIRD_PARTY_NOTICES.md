# Third-party notices

The desktop interface is an original implementation. Its custom styling and
three-panel arrangement were inspired by HoianViewer by nvnprogram:
https://github.com/nvnprogram/HoianViewer

No HoianViewer source code, fonts, textures, logos, or game assets are included.
No Nintendo game files are distributed. Test sounds are generated mathematically.
The optional Nintendo-owned NinDev-Treasure font is not part of the public
source or releases. Users may supply their own copy if permitted by its terms.
Its ownership/terms are not changed by this project's MIT license.

Runtime components:

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

The build script collects the installed packages' license/notice files into the
portable download. Do not remove those files when redistributing the app.
The project's own code is MIT-licensed; see LICENSE. Dependency licenses remain
independent and are not replaced by that license.
