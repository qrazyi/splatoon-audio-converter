"""Appearance-only settings. Never stores audio paths or writes beside inputs."""
from PySide6.QtCore import QSettings
from .theme import DEFAULT_THEME, PALETTES


class AppearanceSettings:
    def __init__(self, path=None):
        self.store = (QSettings(str(path), QSettings.Format.IniFormat) if path else
                      QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                                "SplatoonAudioConverter", "Appearance"))

    @property
    def theme(self):
        value = self.store.value("theme", DEFAULT_THEME)
        if value == "Navy Blue":
            return "Blue"
        return value if value in PALETTES else DEFAULT_THEME

    def save_theme(self, name):
        if name not in PALETTES:
            raise ValueError("Unknown application theme.")
        self.store.setValue("theme", name)
        self.store.sync()
        if self.store.status() != QSettings.Status.NoError:
            raise OSError("The theme could not be saved to your application settings.")
