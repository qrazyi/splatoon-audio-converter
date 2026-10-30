# Portable Windows folder build. Dynamic Qt libraries stay replaceable on disk.
from pathlib import Path
import importlib.metadata

root = Path(SPECPATH)
notices = []
local_fonts = []
font = root / 'local-assets/NinDev-Treasure_00.ttf'
if font.is_file():
    local_fonts.append((str(font), 'splatoon_audio_converter/assets/fonts'))
for dependency in ('numpy', 'zstandard', 'PySide6_Essentials', 'PySide6_Addons', 'shiboken6'):
    distribution = importlib.metadata.distribution(dependency)
    for entry in distribution.files or []:
        if any(word in str(entry).lower() for word in ('license', 'notice', 'copying')):
            source = Path(distribution.locate_file(entry))
            if source.is_file():
                notices.append((str(source), 'licenses/' + dependency + '/' + str(Path(str(entry)).parent)))
a = Analysis(
    [str(root / 'launch.py')],
    pathex=[str(root / 'src')],
    binaries=[],
    datas=[(str(root / 'src/splatoon_audio_converter/native'), 'splatoon_audio_converter/native'),
           (str(root / 'THIRD_PARTY_NOTICES.md'), '.'),
           (str(root / 'licenses'), 'licenses')] + notices + local_fonts,
    hiddenimports=['PySide6.QtMultimedia'],
    excludes=['tkinter', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
              'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtPdf', 'PySide6.Qt3DCore'],
    noarchive=False,
    optimize=1,
)
# Qt 6.12 uses the Windows ICU API. A different program on the build machine's
# PATH can supply an incompatible ICU with the same name (e.g. Poppler's ICU).
# Never redistribute those unversioned Windows system libraries from PATH.
system_icu = {'icuuc.dll', 'icuin.dll', 'icudt.dll'}
a.binaries = [entry for entry in a.binaries if Path(entry[0]).name.lower() not in system_icu]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name='Splatoon Audio Converter', console=False, icon='NONE',
          debug=False, strip=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name='Splatoon Audio Converter', strip=False, upx=False)
