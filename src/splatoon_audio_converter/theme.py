"""Five coordinated application palettes, including the window title bar."""
from dataclasses import dataclass
from string import Template

DEFAULT_THEME = "Beige"


def blend(a, b, amount):
    first, second = [int(a[i:i + 2], 16) for i in (1, 3, 5)], [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x * (1 - amount) + y * amount):02x}" for x, y in zip(first, second))


@dataclass(frozen=True)
class Palette:
    background: str
    surface: str
    accent: str
    on_accent: str
    text: str = "#f7f2ec"

    @property
    def title(self):
        return blend(self.background, self.accent, .12)

    @property
    def line(self):
        return blend(self.background, self.accent, .32)

    @property
    def muted(self):
        return blend(self.text, self.background, .27)


PALETTES = {
    "Beige": Palette("#211d1a", "#39322d", "#d8b18c", "#302219"),
    "Navy Blue": Palette("#101a2a", "#23354b", "#80b4ee", "#11283e"),
    "Brown": Palette("#241712", "#422c22", "#cd9065", "#301a10"),
    "Purple": Palette("#18141e", "#302837", "#b582ed", "#291535"),
    "Green": Palette("#131e18", "#293d30", "#87c99b", "#152e1e"),
}


def palette(name=DEFAULT_THEME):
    return PALETTES.get(name, PALETTES[DEFAULT_THEME])


def active_palette():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    return palette(app.property("themeName") if app else DEFAULT_THEME)


STYLE = Template("""
QWidget { color: $text; font-family: '$font'; font-size: 12px; }
QMainWindow { background: $bg; border: 1px solid $line; }
QWidget#Backdrop { background: $bg; }
QWidget#TitleBar { background: $title; border-bottom: 1px solid $line; }
QLabel#Caption { color: $text; font-size: 11px; }
QToolButton#WindowControl { background: transparent; border: none; border-radius: 4px; }
QToolButton#WindowControl:hover { background: $hover; }
QToolButton#CloseControl { background: transparent; border: none; border-radius: 4px; }
QToolButton#CloseControl:hover { background: #b83a43; }
QFrame#Panel { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 $surface,stop:1 $bottom);
 border: 1px solid $line; border-radius: 15px; }
QLabel { background: transparent; border: none; }
QLabel#Brand { font-size: 22px; font-weight: 800; letter-spacing: 1px; }
QLabel#Section { font-size: 14px; font-weight: 800; letter-spacing: 1px; color: $heading; }
QLabel#Muted { color: $muted; }
QLabel#Tiny { color: $subtle; font-size: 10px; }
QLabel#TrackTitle { font-size: 18px; font-weight: 600; }
QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 $button,stop:1 $button_bottom);
 border: 1px solid $button_line; border-radius: 11px; padding: 8px 12px; min-height: 19px; font-weight: 600; }
QPushButton:hover { background: $hover; border-color: $accent; }
QPushButton:pressed { background: $input; }
QPushButton:disabled { background: $bottom; border-color: $line; color: $disabled; }
QPushButton#Primary { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 $accent_top,stop:1 $accent);
 color: $on_accent; border-color: $accent_top; }
QPushButton#Primary:hover { background: $accent_top; }
QPushButton#Primary:disabled { background: $button; color: $disabled; border-color: $line; }
QPushButton#Link { background: $input; border-color: $button_line; color: $heading; }
QPushButton#Transport { border-radius: 23px; min-width: 46px; min-height: 46px;
 padding: 0; background: $accent; border-color: $accent_top; }
QPushButton#Restart { border-radius: 18px; min-width: 36px; min-height: 36px; padding: 0; }
QPushButton::menu-indicator { subcontrol-position: right center; right: 8px; }
QLineEdit, QComboBox { background: $input; border: 1px solid $button_line; border-radius: 10px;
 padding: 7px 10px; selection-background-color: $selection; min-height: 19px; }
QLineEdit:focus, QComboBox:focus { border-color: $accent; }
QLineEdit:disabled, QComboBox:disabled { color: $disabled; border-color: $line; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: $surface; selection-background-color: $selection; }
QTableWidget { background: $bottom; alternate-background-color: $alternate; border: none;
 gridline-color: $line; selection-background-color: $selection; outline: 0; border-radius: 8px; }
QTableWidget::item { padding: 5px 7px; border-bottom: 1px solid $grid; }
QTableWidget::item:selected { background: $selection; color: $text; }
QHeaderView { background: transparent; }
QHeaderView::section { background: $header; color: $heading; border: none;
 padding: 9px 7px; font-size: 10px; font-weight: 600; letter-spacing: .6px; }
QScrollBar:vertical { background: $input; width: 9px; border-radius: 4px; margin: 0; }
QScrollBar::handle:vertical { background: $handle; border-radius: 4px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { height: 9px; background: $input; }
QScrollBar::handle:horizontal { background: $handle; border-radius: 4px; min-width: 28px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QSlider::groove:horizontal { height: 6px; background: $input; border-radius: 3px; }
QSlider::sub-page:horizontal { background: $accent; border-radius: 3px; }
QSlider::handle:horizontal { background: $accent_top; width: 14px; margin: -4px 0; border-radius: 7px; }
QMenu { background: $surface; border: 1px solid $line; padding: 5px; }
QMenu::item { padding: 8px 25px; border-radius: 4px; }
QMenu::item:selected { background: $selection; }
QPlainTextEdit { background: $input; border: none; color: $muted; font-size: 10px; }
QProgressBar { border: none; background: $input; border-radius: 2px; height: 4px; }
QProgressBar::chunk { background: $accent; border-radius: 2px; }
QSplitter::handle { background: transparent; width: 9px; height: 9px; }
QStatusBar { background: $bg; color: $muted; border-top: 1px solid $line; }
QStatusBar::item { border: none; }
QToolTip { background: $surface; color: $text; border: 1px solid $accent; padding: 6px; }
QMessageBox, QFileDialog { background: $bottom; }
""")


def stylesheet(name, family):
    p = palette(name)
    return STYLE.substitute(font=family.replace("\\", "\\\\").replace("'", "\\'"),
        bg=p.background, surface=p.surface, bottom=blend(p.surface, p.background, .55),
        title=p.title, line=p.line, text=p.text, accent=p.accent, on_accent=p.on_accent,
        muted=p.muted, subtle=blend(p.text, p.background, .42), heading=blend(p.accent, p.text, .6),
        button=blend(p.surface, p.accent, .25), button_bottom=blend(p.surface, p.background, .1),
        button_line=blend(p.surface, p.accent, .45), hover=blend(p.surface, p.accent, .4),
        input=blend(p.background, "#000000", .08), disabled=blend(p.text, p.background, .62),
        accent_top=blend(p.accent, "#ffffff", .25), selection=blend(p.background, p.accent, .5),
        alternate=blend(p.surface, p.background, .3), grid=blend(p.background, p.accent, .14),
        header=blend(p.surface, p.accent, .08), handle=blend(p.background, p.accent, .55))


def apply_theme(app, name):
    name = name if name in PALETTES else DEFAULT_THEME
    app.setProperty("themeName", name)
    app.setStyleSheet(stylesheet(name, app.property("interfaceFont") or "Segoe UI"))
    for window in app.topLevelWidgets():
        window.update()
    return name
