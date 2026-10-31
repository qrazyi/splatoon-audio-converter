import importlib.util
import io
from pathlib import Path
import unittest
import zipfile

spec = importlib.util.spec_from_file_location("check_privacy", Path(__file__).resolve().parents[1] / "scripts/check_privacy.py")
privacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(privacy)


class PrivacyTests(unittest.TestCase):
    def test_native_executable_does_not_need_pyinstaller_reader(self):
        self.assertFalse(privacy.is_pyinstaller(b"MZ managed executable"))
        self.assertTrue(privacy.is_pyinstaller(b"MZ data MEI\x0c\x0b\x0a\x0b\x0e archive"))
    def test_personal_paths_ascii_escaped_and_utf16(self):
        value = "C:" + "\\Users\\" + Path.home().name + "\\Desktop\\private.txt"
        for data in (value.encode(), value.replace("\\", "\\\\").encode(), value.encode("utf-16-le")):
            self.assertTrue(privacy.matches(data))

    def test_application_cannot_embed_upstream_examples(self):
        value = ("C:" + "/Users/" + "qt/work/build.pdb").encode()
        self.assertFalse(privacy.matches(value))
        self.assertTrue(privacy.matches(value, own_code=True))

    def test_unknown_profile_in_dependency_fails(self):
        value = ("/home/" + "private-author" + "/project").encode()
        self.assertTrue(privacy.matches(value))

    def test_portable_relative_names_pass(self):
        self.assertFalse(privacy.matches(b"splatoon_audio_converter/ui.py", own_code=True))

    def test_compressed_libraries_are_scanned_after_decompression(self):
        stream = io.BytesIO()
        private = ("C:" + "/Users/" + Path.home().name + "/Desktop/private").encode()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("module.pyc", private)
        entries = dict(privacy.payloads("base_library.zip", stream.getvalue()))
        self.assertTrue(privacy.matches(entries["base_library.zip!module.pyc"]))


if __name__ == "__main__":
    unittest.main()
