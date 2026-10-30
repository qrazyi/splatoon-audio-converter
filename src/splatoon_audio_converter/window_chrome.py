"""Themeable title bar with native drag/resize and normal window controls."""
from PySide6.QtCore import QEvent, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMainWindow, QToolButton, QWidget

from .theme import active_palette


def resize_edges(x, y, width, height, border=5):
    edges = Qt.Edge(0)
    if not (0 <= x < width and 0 <= y < height):
        return edges
    if x < border:
        edges |= Qt.Edge.LeftEdge
    elif x >= width - border:
        edges |= Qt.Edge.RightEdge
    if y < border:
        edges |= Qt.Edge.TopEdge
    elif y >= height - border:
        edges |= Qt.Edge.BottomEdge
    return edges


class WindowControl(QToolButton):
    def __init__(self, kind, window):
        super().__init__(window)
        self.kind, self.owner = kind, window
        self.setObjectName("CloseControl" if kind == "close" else "WindowControl")
        self.setFixedSize(43, 30)
        self.setAccessibleName({"minimize": "Minimize", "maximize": "Maximize or restore", "close": "Close"}[kind])
        self.setToolTip(self.accessibleName())
        self.clicked.connect({"minimize": window.showMinimized,
                              "maximize": window.toggle_maximized, "close": window.close}[kind])

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(active_palette().text), 1.5))
        x, y = self.width() / 2, self.height() / 2
        if self.kind == "minimize":
            p.drawLine(round(x - 5), round(y + 2), round(x + 5), round(y + 2))
        elif self.kind == "close":
            p.drawLine(round(x - 4), round(y - 4), round(x + 4), round(y + 4))
            p.drawLine(round(x - 4), round(y + 4), round(x + 4), round(y - 4))
        elif self.owner.isMaximized():
            p.drawRect(QRectF(x - 3, y - 5, 8, 8))
            p.fillRect(QRectF(x - 5, y - 3, 8, 8), QColor(active_palette().title))
            p.drawRect(QRectF(x - 5, y - 3, 8, 8))
        else:
            p.drawRect(QRectF(x - 4, y - 4, 8, 8))


class TitleBar(QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.owner = window
        self.setObjectName("TitleBar")
        self.setFixedHeight(38)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(13, 3, 4, 3)
        layout.setSpacing(2)
        self.caption = QLabel(window.windowTitle())
        self.caption.setObjectName("Caption")
        window.windowTitleChanged.connect(self.caption.setText)
        layout.addWidget(self.caption)
        layout.addStretch()
        for kind in ("minimize", "maximize", "close"):
            layout.addWidget(WindowControl(kind, window))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.owner.try_resize(event.globalPosition().toPoint()) and self.owner.windowHandle():
                self.owner.windowHandle().startSystemMove()
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.owner.toggle_maximized()
            event.accept()


class ThemedWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setContentsMargins(4, 4, 4, 4)
        self.setMouseTracking(True)
        self.titlebar = TitleBar(self)
        self.setMenuWidget(self.titlebar)
        QApplication.instance().installEventFilter(self)

    def toggle_maximized(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def try_resize(self, point):
        if self.isMaximized() or self.isFullScreen() or not self.windowHandle():
            return False
        local = self.mapFromGlobal(point)
        edges = resize_edges(local.x(), local.y(), self.width(), self.height())
        return bool(edges and self.windowHandle().startSystemResize(edges))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.try_resize(event.globalPosition().toPoint()):
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position()
        self.update_resize_cursor(pos)
        super().mouseMoveEvent(event)

    def update_resize_cursor(self, pos):
        edges = resize_edges(pos.x(), pos.y(), self.width(), self.height()) if not (self.isMaximized() or self.isFullScreen()) else Qt.Edge(0)
        horizontal = edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge)
        vertical = edges & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge)
        if horizontal and vertical:
            forward = bool(edges & Qt.Edge.LeftEdge) == bool(edges & Qt.Edge.TopEdge)
            cursor = Qt.CursorShape.SizeFDiagCursor if forward else Qt.CursorShape.SizeBDiagCursor
        else:
            cursor = Qt.CursorShape.SizeHorCursor if horizontal else Qt.CursorShape.SizeVerCursor if vertical else Qt.CursorShape.ArrowCursor
        if edges:
            self.setCursor(cursor)
        else:
            self.unsetCursor()  # Do not leak an edge-resize cursor into children.

    def eventFilter(self, watched, event):
        if isinstance(watched, QWidget) and watched.window() is self:
            if event.type() in (QEvent.Type.MouseMove, QEvent.Type.Enter):
                if hasattr(event, "globalPosition"):
                    self.update_resize_cursor(self.mapFromGlobal(event.globalPosition().toPoint()))
            elif watched is self and event.type() in (QEvent.Type.Leave, QEvent.Type.WindowDeactivate):
                self.unsetCursor()
        return super().eventFilter(watched, event)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            self.unsetCursor()
            margin = 0 if self.isMaximized() or self.isFullScreen() else 4
            self.setContentsMargins(margin, margin, margin, margin)
            self.titlebar.update()
        super().changeEvent(event)
