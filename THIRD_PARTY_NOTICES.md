# Third-party notices

The supported download uses the original Qt/Python application. The smaller
package omits unused FFmpeg video backends and QML/PDF/3D components; it retains
Python, Qt Widgets/Multimedia's Windows PCM backend, NumPy and the supplied font.
The unused `native-app/` experiment is not part of this download.

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
- **FFmpeg** — not included in the smaller package. Existing complete Qt license
  bundles may still contain notices for it. Source: https://ffmpeg.org/
- **charset-normalizer**, when collected by the build — MIT license; its
  notice is included in the runtime licenses folder.
  Source: https://github.com/jawah/charset_normalizer

The build script collects the installed packages' license/notice files into the
portable download. Do not remove those files when redistributing the app.
The project's own code is MIT-licensed; see LICENSE. Dependency licenses remain
independent and are not replaced by that license.
