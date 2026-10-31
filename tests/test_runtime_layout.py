import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from runtime_layout import omit_runtime


class RuntimeLayoutTests(unittest.TestCase):
    def test_keep_interface_and_audio_dependencies(self):
        for name in ("Splatoon Audio Converter.exe", "_internal/Qt6Core.dll", "_internal/Qt6Gui.dll",
                     "_internal/Qt6Widgets.dll", "_internal/Qt6Multimedia.dll", "_internal/Qt6Network.dll",
                     "_internal/PySide6/plugins/platforms/qwindows.dll",
                     "_internal/PySide6/plugins/multimedia/windowsmediaplugin.dll",
                     "_internal/numpy.libs/libscipy_openblas64.dll",
                     "_internal/splatoon_audio_converter/assets/fonts/NinDev-Treasure_00.ttf"):
            self.assertFalse(omit_runtime(name), name)

    def test_omit_only_optional_components(self):
        for name in ("_internal/icudt78.dll", "_internal/PySide6/opengl32sw.dll",
                     "_internal/Qt6Quick.dll", "_internal/Qt6QmlModels.dll", "_internal/Qt6Pdf.dll",
                     "_internal/PySide6/plugins/multimedia/ffmpegmediaplugin.dll",
                     "_internal/PySide6/plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll",
                     "_internal/avcodec-63.dll", "_internal/PySide6/plugins/imageformats/qpdf.dll"):
            self.assertTrue(omit_runtime(name), name)
