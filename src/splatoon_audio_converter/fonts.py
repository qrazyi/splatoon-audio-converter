"""Load the supplied interface font without storing its original location."""
from pathlib import Path
import sys

from PySide6.QtGui import QFont, QFontDatabase

from .theme import apply_theme
from .preferences import AppearanceSettings


def configure(app, theme_name=None):
    package = Path(__file__).resolve().parent
    candidates = [package / "assets/fonts/NinDev-Treasure_00.ttf"]
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).parent / "fonts/NinDev-Treasure_00.ttf")
    else:
        candidates += [package.parents[1] / "local-assets/NinDev-Treasure_00.ttf",
                       package.parents[1] / "fonts/NinDev-Treasure_00.ttf"]
    family = "Segoe UI" if sys.platform == "win32" else "sans-serif"
    for path in candidates:
        if path.is_file():
            identifier = QFontDatabase.addApplicationFont(str(path))
            families = QFontDatabase.applicationFontFamilies(identifier) if identifier >= 0 else []
            if families:
                family = families[0]
                break
    app.setFont(QFont(family, 11))
    app.setStyle("Fusion")
    app.setProperty("interfaceFont", family)
    apply_theme(app, theme_name or AppearanceSettings().theme)
    return family
