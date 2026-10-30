"""Original purple desktop theme; no HoianViewer source or artwork used."""

STYLE = """
QWidget { color: #f6f1ff; font-family: 'UI_FONT'; font-size: 12px; }
QMainWindow, QWidget#Backdrop { background: #18141e; }
QFrame#Panel { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
    stop:0 #302837, stop:1 #211c29); border: 1px solid #50415f; border-radius: 15px; }
QFrame#Inset { background: #211a2b; border: 1px solid #50415f; border-radius: 11px; }
QLabel { background: transparent; border: none; }
QLabel#Brand { font-size: 22px; font-weight: 800; letter-spacing: 1px; }
QLabel#Section { font-size: 14px; font-weight: 800; letter-spacing: 1px; color: #e8d6ff; }
QLabel#Muted { color: #c5b8d4; }
QLabel#Tiny { color: #ae9ebf; font-size: 10px; }
QLabel#TrackTitle { font-size: 18px; font-weight: 600; }
QLabel#Badge { color: #ead6ff; background: #4d3269; border: 1px solid #835da5;
    border-radius: 8px; padding: 4px 9px; font-size: 12px; }
QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
    stop:0 #5a456f, stop:1 #3c2c4e); border: 1px solid #7e6097; border-radius: 11px;
    padding: 8px 12px; min-height: 19px; font-weight: 600; }
QPushButton:hover { background: #70508a; border-color: #c396f0; }
QPushButton:pressed { background: #33203f; }
QPushButton:disabled { background: #302738; border-color: #493954; color: #8a7897; }
QPushButton#Primary { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
    stop:0 #bf8bfa, stop:1 #8350cf); color: #fff9ff; border-color: #cba1f5; }
QPushButton#Primary:hover { background: #b47bf0; }
QPushButton#Primary:disabled { background: #533767; color: #ac91bb; border-color: #725184; }
QPushButton#Link { background: #2e223a; border-color: #705186; color: #dcb7ff; }
QPushButton#Transport { border-radius: 23px; min-width: 46px; min-height: 46px;
    padding: 0; background: #b582ed; color: #251531; border-color: #dfbaff; }
QPushButton#Restart { border-radius: 18px; min-width: 36px; min-height: 36px; padding: 0; }
QLineEdit, QComboBox { background: #1f1727; border: 1px solid #674e7d; border-radius: 10px;
    padding: 7px 10px; selection-background-color: #8252b3; min-height: 19px; }
QLineEdit:focus, QComboBox:focus { border-color: #bb8cf0; }
QLineEdit:disabled, QComboBox:disabled { color: #a08aaf; border-color: #4e3a5c; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: #30213c; selection-background-color: #704b93; }
QTableWidget { background: #251d2e; alternate-background-color: #2c2236; border: none;
    gridline-color: #473252; selection-background-color: #6b428e; outline: 0;
    border-radius: 8px; }
QTableWidget::item { padding: 5px 7px; border-bottom: 1px solid #3d2e49; }
QTableWidget::item:selected { background: #6b428e; color: #ffffff; }
QHeaderView { background: transparent; }
QHeaderView::section { background: #382941; color: #d6b5ed; border: none;
    padding: 9px 7px; font-size: 10px; font-weight: 600; letter-spacing: .6px; }
QScrollBar:vertical { background: #211927; width: 9px; border-radius: 4px; margin: 0; }
QScrollBar::handle:vertical { background: #806394; border-radius: 4px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { height: 9px; background: #211927; }
QScrollBar::handle:horizontal { background: #806394; border-radius: 4px; min-width: 28px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QSlider::groove:horizontal { height: 6px; background: #19111f; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #a676df; border-radius: 3px; }
QSlider::handle:horizontal { background: #e9ceff; width: 14px; margin: -4px 0; border-radius: 7px; }
QMenu { background: #30213c; border: 1px solid #76518c; padding: 5px; }
QMenu::item { padding: 7px 25px; border-radius: 4px; }
QMenu::item:selected { background: #704b93; }
QPlainTextEdit { background: #201726; border: none; color: #d7c2e8; font-size: 10px; }
QProgressBar { border: none; background: #201726; border-radius: 2px; height: 4px; }
QProgressBar::chunk { background: #b582ed; border-radius: 2px; }
QSplitter::handle { background: transparent; width: 9px; height: 9px; }
QStatusBar { background: #18141e; color: #c0a4d4; border-top: 1px solid #493352; }
QStatusBar::item { border: none; }
QToolTip { background: #382344; color: #f6e9ff; border: 1px solid #a575c4; padding: 6px; }
QMessageBox, QFileDialog { background: #291d32; }
"""
