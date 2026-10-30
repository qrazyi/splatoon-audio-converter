import importlib.util
from pathlib import Path
import tempfile
import unittest
import shutil


spec = importlib.util.spec_from_file_location("package_release", Path(__file__).resolve().parents[1] / "scripts/package_release.py")
package_release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package_release)


class PublicPackagingTests(unittest.TestCase):
    def test_only_executable_and_runtime_are_at_download_root(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("Splatoon Audio Converter.exe", "START HERE.txt", "LICENSE",
                         "THIRD_PARTY_NOTICES.md", "README.md", "fonts/README.md",
                         "_internal/python312.dll", "_internal/native/.gitkeep",
                         "_internal/licenses/application/LICENSE",
                         "_internal/licenses/application/THIRD_PARTY_NOTICES.md",
                         "_internal/licenses/Qt/README.txt"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fixture")
            actual = {p.relative_to(root).as_posix() for p in package_release.release_files(root)}
            self.assertNotIn("README.md", actual)
            self.assertNotIn("fonts/README.md", actual)
            self.assertNotIn("START HERE.txt", actual)
            self.assertNotIn("LICENSE", actual)
            self.assertNotIn("THIRD_PARTY_NOTICES.md", actual)
            self.assertEqual({name for name in actual if "/" not in name}, {"Splatoon Audio Converter.exe"})
            self.assertIn("_internal/licenses/application/LICENSE", actual)
            self.assertIn("_internal/licenses/Qt/README.txt", actual)
            self.assertIn("_internal/python312.dll", actual)

    def test_private_fonts_settings_logs_audio_and_unknown_root_files_are_rejected(self):
        for name in ("_internal/assets/font.ttf", "_internal/config.json", "theme.ini",
                     "activity.log", "example.bfstm", "local-assets/font.otf", "personal.txt"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"private test fixture")
                with self.assertRaisesRegex(ValueError, "Non-release file"):
                    list(package_release.release_files(Path(folder)))

    def test_only_the_supplied_interface_font_is_allowed_at_its_runtime_location(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            font = root / package_release.RUNTIME_FONT
            font.parent.mkdir(parents=True)
            shutil.copyfile(package_release.ROOT / package_release.BUNDLED_FONT, font)
            self.assertIn(font, list(package_release.release_files(root)))
            font.write_bytes(b"unapproved replacement")
            with self.assertRaisesRegex(ValueError, "Non-release file"):
                list(package_release.release_files(root))

    def test_source_package_contains_the_font_without_private_local_assets(self):
        names = {p.relative_to(package_release.ROOT).as_posix() for p in package_release.source_files()}
        self.assertIn(package_release.BUNDLED_FONT, names)
        self.assertFalse(any("local-assets" in name for name in names))
