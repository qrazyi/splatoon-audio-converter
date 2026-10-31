"""Saving must persist, not merely dismiss the warning or update memory."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import uuid

from PySide6.QtCore import QSettings

from splatoon_audio_converter import preferences
from splatoon_audio_converter.preferences import AppearanceSettings


class PreferenceTests(unittest.TestCase):
    def test_a_previous_error_does_not_poison_later_saves(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = AppearanceSettings(Path(folder) / "theme.ini")
            stale = Mock()
            stale.status.return_value = QSettings.Status.AccessError
            settings.store = stale
            settings.save_theme("Eco")
            stale.setValue.assert_not_called()
            self.assertEqual(AppearanceSettings(Path(folder) / "theme.ini").theme, "Eco")

    def test_transient_write_failure_is_retried_with_a_fresh_object(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = AppearanceSettings(Path(folder) / "theme.ini")
            factory = settings._new_store
            failed = Mock()
            failed.status.return_value = QSettings.Status.AccessError
            with patch.object(settings, "_new_store", side_effect=[failed, factory(), factory()]):
                settings.save_theme("Aqua")
            self.assertEqual(AppearanceSettings(Path(folder) / "theme.ini").theme, "Aqua")

    def test_failed_write_is_still_reported_not_hidden(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = AppearanceSettings(Path(folder) / "theme.ini")
            failed = Mock()
            failed.status.return_value = QSettings.Status.AccessError
            with patch.object(settings, "_new_store", return_value=failed):
                with self.assertRaises(OSError):
                    settings.save_theme("Beige")

    def test_readback_must_confirm_the_requested_value(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = AppearanceSettings(Path(folder) / "theme.ini")
            wrong = Mock()
            wrong.status.return_value = QSettings.Status.NoError
            wrong.value.return_value = "Dorfic"
            with patch.object(settings, "_new_store", return_value=wrong):
                with self.assertRaises(OSError):
                    settings.save_theme("Eco")

    def test_invalid_value_types_fall_back_safely(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = AppearanceSettings(Path(folder) / "theme.ini")
            settings.store.setValue("theme", ["not", "a", "theme"])
            self.assertEqual(settings.theme, "Dorfic")
            with self.assertRaises(ValueError):
                settings.save_theme(["Eco"])

    @unittest.skipUnless(sys.platform == "win32", "Windows registry migration")
    def test_windows_registry_migrates_old_ini_and_survives_another_process(self):
        # Isolated app name: never clear or alter the developer's real settings.
        app_name = "PreferenceTests-" + uuid.uuid4().hex
        with tempfile.TemporaryDirectory() as folder, patch.object(preferences, "APPLICATION", app_name):
            path = Path(folder) / "old.ini"
            legacy = QSettings(str(path), QSettings.Format.IniFormat)
            legacy.setValue("theme", "Aqua")
            legacy.sync()
            factory = preferences.QSettings

            def stores(*args):
                if args and args[0] == QSettings.Format.IniFormat:
                    return factory(str(path), QSettings.Format.IniFormat)
                return factory(*args)

            try:
                with patch.object(preferences, "QSettings", side_effect=stores,
                                  wraps=QSettings):
                    # Wrapped enums are not Qt enums; restore enum namespaces.
                    preferences.QSettings.Format = QSettings.Format
                    preferences.QSettings.Scope = QSettings.Scope
                    preferences.QSettings.Status = QSettings.Status
                    settings = AppearanceSettings()
                    self.assertEqual(settings.store.format(), QSettings.Format.NativeFormat)
                    self.assertFalse(settings.store.fallbacksEnabled())
                    self.assertEqual(settings.theme, "Aqua")
                    settings.save_theme("Beige")
                    self.assertEqual(legacy.value("theme"), "Aqua")
                    self.assertEqual(settings.store.allKeys(), ["theme"])
                script = (
                    "from splatoon_audio_converter import preferences as p; "
                    "p.APPLICATION=" + repr(app_name) + "; "
                    "assert p.AppearanceSettings().theme=='Beige', 'Theme did not persist'"
                )
                environment = os.environ.copy()
                environment["PYTHONPATH"] = os.pathsep.join(map(str, sys.path))
                result = subprocess.run([sys.executable, "-c", script], env=environment,
                                        capture_output=True, text=True, timeout=20,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.assertEqual(result.returncode, 0, result.stderr)
            finally:
                registry = QSettings(QSettings.Format.NativeFormat, QSettings.Scope.UserScope,
                                     preferences.ORGANIZATION, app_name)
                registry.clear()
                registry.sync()


if __name__ == "__main__":
    unittest.main()
