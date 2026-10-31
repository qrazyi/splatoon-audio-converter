"""Appearance-only settings. Never stores audio paths or writes beside inputs."""
import sys

from PySide6.QtCore import QSettings
from .theme import DEFAULT_THEME, PALETTES

ORGANIZATION = "SplatoonAudioConverter"
APPLICATION = "Appearance"


class AppearanceSettings:
    def __init__(self, path=None):
        self._path = str(path) if path is not None else None
        self._organization, self._application = ORGANIZATION, APPLICATION
        # The Windows registry does not need a writable roaming folder, INI
        # lock file or atomic file rename. Explicit test/portable INI paths
        # retain their original behavior; nothing is written beside game files.
        self._native = self._path is None and sys.platform == "win32"
        self.store = self._new_store()

    def _new_store(self):
        if self._path is not None:
            store = QSettings(self._path, QSettings.Format.IniFormat)
        else:
            format_ = QSettings.Format.NativeFormat if self._native else QSettings.Format.IniFormat
            store = QSettings(format_, QSettings.Scope.UserScope,
                              self._organization, self._application)
        # Never inherit or try to modify machine-wide settings.
        store.setFallbacksEnabled(False)
        return store

    @staticmethod
    def _valid(value):
        return isinstance(value, str) and value in PALETTES

    @property
    def theme(self):
        value = self.store.value("theme")
        if value is None and self._native:
            # Read the previous INI preference until the first successful native
            # save. Do not rewrite or repair a user's existing configuration.
            legacy = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                               self._organization, self._application)
            legacy.setFallbacksEnabled(False)
            value = legacy.value("theme")
        return value if self._valid(value) else DEFAULT_THEME

    def save_theme(self, name):
        if not self._valid(name):
            raise ValueError("Unknown application theme.")
        # QSettings.status() records the first error for that object. Reusing a
        # previously failed object made later saves report an old error forever.
        # Use fresh objects, retry once, and verify the value after sync instead.
        for _ in range(2):
            writer = self._new_store()
            writer.setValue("theme", name)
            writer.sync()
            if writer.status() != QSettings.Status.NoError:
                continue
            reader = self._new_store()
            reader.sync()
            if reader.status() == QSettings.Status.NoError and reader.value("theme") == name:
                self.store = reader
                return
        raise OSError("The theme could not be saved to your application settings.")
