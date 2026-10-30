from pathlib import Path
import tempfile
import unittest

from PySide6.QtCore import Qt
from splatoon_audio_converter.preferences import AppearanceSettings
from splatoon_audio_converter.theme import DEFAULT_THEME, PALETTES, palette, stylesheet
from splatoon_audio_converter.window_chrome import resize_edges


class ThemeTests(unittest.TestCase):
    def test_exact_theme_choices_and_default(self):
        self.assertEqual(list(PALETTES), ["Aqua", "Beige", "Dark Aero", "Dorfic", "Eco"])
        self.assertEqual(list(PALETTES), sorted(PALETTES))
        self.assertEqual(DEFAULT_THEME, "Dorfic")
        self.assertEqual(palette("unknown"), palette("Dorfic"))

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

    def test_exact_requested_gradient_colors_and_no_glass_styles(self):
        expected = {"Dark Aero": ("#1c1c1c", "#4f4f4f"),
                    "Dorfic": ("#f07902", "#fbcc11"),
                    "Eco": ("#4ae072", "#4ce6a3"),
                    "Aqua": ("#66e2f2", "#6676f2")}
        for name, colors in expected.items():
            self.assertEqual(palette(name).gradient, colors)
            style = stylesheet(name, "Test Font")
            self.assertIn("stop:0 " + colors[0] + ",stop:1 " + colors[1], style)
            self.assertNotIn("qradialgradient", style)
            self.assertNotIn("rgba(", style)
            self.assertIn("border-radius: 14px", style)

    def test_preferences_persist_only_the_theme_and_fall_back_safely(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "appearance.ini"
            settings = AppearanceSettings(path)
            self.assertEqual(settings.theme, "Dorfic")
            settings.save_theme("Eco")
            self.assertEqual(AppearanceSettings(path).theme, "Eco")
            self.assertNotIn("path=", path.read_text())
            with self.assertRaises(ValueError):
                settings.save_theme("Invalid")
            settings.store.setValue("theme", "corrupt")
            self.assertEqual(settings.theme, "Dorfic")
            for removed in ("Brown", "Navy Blue", "Blue", "Green", "Orange", "Purple", "Yellow"):
                settings.store.setValue("theme", removed)
                self.assertEqual(settings.theme, "Dorfic")
            settings.save_theme("Beige")
            self.assertEqual(AppearanceSettings(path).theme, "Beige")

    def test_frameless_border_has_correct_native_resize_edges(self):
        self.assertEqual(resize_edges(1, 1, 100, 100), Qt.Edge.LeftEdge | Qt.Edge.TopEdge)
        self.assertEqual(resize_edges(99, 99, 100, 100), Qt.Edge.RightEdge | Qt.Edge.BottomEdge)
        self.assertEqual(resize_edges(50, 50, 100, 100), Qt.Edge(0))
        self.assertEqual(resize_edges(-1, 50, 100, 100), Qt.Edge(0))
        self.assertEqual(resize_edges(101, 50, 100, 100), Qt.Edge(0))
