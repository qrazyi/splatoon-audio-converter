from pathlib import Path
import tempfile
import unittest

from PySide6.QtCore import Qt
from splatoon_audio_converter.preferences import AppearanceSettings
from splatoon_audio_converter.theme import DEFAULT_THEME, PALETTES, palette, stylesheet
from splatoon_audio_converter.window_chrome import resize_edges


class ThemeTests(unittest.TestCase):
    def test_exact_theme_choices_and_default(self):
        self.assertEqual(list(PALETTES), ["Beige", "Navy Blue", "Brown", "Purple", "Green"])
        self.assertEqual(DEFAULT_THEME, "Beige")
        self.assertEqual(palette("unknown"), palette("Beige"))

    def test_each_theme_styles_the_titlebar_and_full_interface(self):
        styles = set()
        for name in PALETTES:
            style = stylesheet(name, "Test Font")
            self.assertIn(palette(name).title, style)
            self.assertIn("QWidget#TitleBar", style)
            self.assertIn(palette(name).accent, style)
            self.assertNotIn("$", style)
            styles.add(style)
        self.assertEqual(len(styles), 5)

    def test_preferences_persist_only_the_theme_and_fall_back_safely(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "appearance.ini"
            settings = AppearanceSettings(path)
            self.assertEqual(settings.theme, "Beige")
            settings.save_theme("Green")
            self.assertEqual(AppearanceSettings(path).theme, "Green")
            self.assertNotIn("path=", path.read_text())
            with self.assertRaises(ValueError):
                settings.save_theme("Invalid")
            settings.store.setValue("theme", "corrupt")
            self.assertEqual(settings.theme, "Beige")

    def test_frameless_border_has_correct_native_resize_edges(self):
        self.assertEqual(resize_edges(1, 1, 100, 100), Qt.Edge.LeftEdge | Qt.Edge.TopEdge)
        self.assertEqual(resize_edges(99, 99, 100, 100), Qt.Edge.RightEdge | Qt.Edge.BottomEdge)
        self.assertEqual(resize_edges(50, 50, 100, 100), Qt.Edge(0))
