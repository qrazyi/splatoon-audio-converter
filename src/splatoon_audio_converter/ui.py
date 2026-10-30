"""A native desktop audio workbench with an independently built warm-dark UI."""
from __future__ import annotations

import argparse
import math
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, QTimer, QUrl, Signal, Slot, QRectF
from PySide6.QtGui import QAction, QActionGroup, QColor, QDesktopServices, QFont, QIcon, QKeySequence, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMenu, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QScrollArea, QSlider, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QAbstractItemView,
)

from . import __version__, updates
from .core import BarsDocument, Track, bars_base_name, bars_zs_name, bfstm_name, bwav_name, read_pcm16
from .preview import Preview, prepare
from .fonts import configure
from .playback import PreviewPlayer
from .preferences import AppearanceSettings
from .theme import PALETTES, active_palette, apply_theme, blend
from .window_chrome import ThemedWindow

APP_NAME = "Splatoon Audio Converter"
FILTERS = ("Splatoon audio (*.bars.zs *.bars *.bwav *.bwav.zs *.bfstm *.bfstm.zs);;"
           "BARS archives (*.bars *.bars.zs);;BWAV sounds (*.bwav *.bwav.zs);;"
           "BFSTM music (*.bfstm *.bfstm.zs);;All files (*)")


def clock(seconds: float) -> str:
    ticks = round(max(0.0, seconds) * 100)
    return f"{ticks // 6000:02d}:{ticks // 100 % 60:02d}.{ticks % 100:02d}"


def db(value: float) -> str:
    return "Silent" if not math.isfinite(value) else f"{value:.1f} dBFS"


def label(text: str, style: str = "", wrap: bool = False) -> QLabel:
    widget = QLabel(text)
    if style:
        widget.setObjectName(style)
    widget.setWordWrap(wrap)
    return widget


def button(text: str, callback, style: str = "") -> QPushButton:
    widget = QPushButton(text)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if style:
        widget.setObjectName(style)
    widget.clicked.connect(callback)
    return widget


def playback_icon(shape="play", color=None):
    color = color or active_palette().on_accent
    pixmap = QPixmap(22, 22)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    if shape == "play":
        path = QPainterPath()
        path.moveTo(7, 4)
        path.lineTo(18, 11)
        path.lineTo(7, 18)
        path.closeSubpath()
        painter.drawPath(path)
    elif shape == "pause":
        painter.drawRoundedRect(5, 4, 4, 14, 1, 1)
        painter.drawRoundedRect(13, 4, 4, 14, 1, 1)
    elif shape == "restart":
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(color), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(QRectF(4, 4, 14, 14), 45 * 16, 285 * 16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        arrow = QPainterPath()
        arrow.moveTo(12.8, 14.1)
        arrow.lineTo(18.5, 16)
        arrow.lineTo(18, 9.8)
        arrow.closeSubpath()
        painter.drawPath(arrow)
    painter.end()
    return QIcon(pixmap)


class Panel(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("Panel")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(15, 15, 15, 15)
        self.body.setSpacing(11)
        if title:
            self.body.addWidget(label(title, "Section"))


class Backdrop(QWidget):
    """Subtle procedural audio-line motif, not copied game/viewer artwork."""
    def __init__(self):
        super().__init__()
        self.setObjectName("Backdrop")

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        palette = active_palette()
        painter.fillRect(self.rect(), QColor(palette.background))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        motif = QColor(palette.accent)
        motif.setAlpha(23)
        painter.setPen(QPen(motif, 1.1))
        for y in range(-30, self.height() + 50, 84):
            path = QPainterPath()
            path.moveTo(-20, y)
            for x in range(-20, self.width() + 70, 70):
                path.cubicTo(x + 15, y - 32, x + 40, y + 32, x + 70, y)
            painter.drawPath(path)


class Waveform(QWidget):
    seek = Signal(float)

    def __init__(self):
        super().__init__()
        self.peaks = None
        self.position = 0.0
        self.duration = 0.0
        self.message = "Select a sound to see its waveform"
        self.setMinimumHeight(190)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName("Audio waveform. Click to seek.")

    def set_preview(self, preview: Preview):
        self.peaks, self.duration = preview.peaks, preview.duration
        self.position = 0
        self.update()

    def clear(self, message="Select a sound to see its waveform"):
        self.peaks = None
        self.duration = self.position = 0
        self.message = message
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        palette = active_palette()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(blend(palette.background, "#000000", .08)))
        p.setPen(QPen(QColor(palette.line), 1))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 11, 11)
        area = self.rect().adjusted(30, 24, -20, -25)
        for i in range(5):
            y = area.top() + area.height() * i / 4
            p.setPen(QPen(QColor(blend(palette.background, palette.accent, .14)), 1))
            p.drawLine(area.left(), round(y), area.right(), round(y))
        for i in range(1, 8):
            x = area.left() + area.width() * i / 8
            p.setPen(QPen(QColor(blend(palette.background, palette.accent, .10)), 1))
            p.drawLine(round(x), area.top(), round(x), area.bottom())
        if self.peaks is None:
            p.setPen(QColor(palette.muted))
            p.drawText(area, Qt.AlignmentFlag.AlignCenter, self.message)
            return
        count = min(len(self.peaks), max(1, area.width() // 3))
        indices = np.linspace(0, len(self.peaks) - 1, count).astype(int)
        for i, index in enumerate(indices):
            x = area.left() + area.width() * i / max(1, count - 1)
            height = max(1.5, float(self.peaks[index]) * area.height() * .45)
            p.setPen(QPen(QColor(blend(palette.accent, palette.text, .65)) if i / max(1, count) <= self.position else QColor(palette.accent), 1.5))
            p.drawLine(round(x), round(area.center().y() - height), round(x), round(area.center().y() + height))
        x = area.left() + self.position * area.width()
        p.setPen(QPen(QColor(palette.text), 1.3))
        p.drawLine(round(x), area.top(), round(x), area.bottom())
        p.setPen(QColor(palette.muted))
        tick_font = QFont(self.font())
        tick_font.setPixelSize(12)
        p.setFont(tick_font)
        p.drawText(12, 18, "0 dBFS")
        p.drawText(12, self.height() - 9, "0:00")
        p.drawText(self.width() - 67, self.height() - 9, clock(self.duration).split(".")[0])

    def mousePressEvent(self, event):
        if self.peaks is not None:
            fraction = max(0.0, min(1.0, (event.position().x() - 30) / max(1, self.width() - 50)))
            self.seek.emit(fraction)


class JobSignals(QObject):
    done = Signal(object, object)
    failed = Signal(str)
    progress = Signal(str)


class Job(QRunnable):
    def __init__(self, operation, callback):
        super().__init__()
        self.operation, self.callback = operation, callback
        self.signals = JobSignals()

    @Slot()
    def run(self):
        try:
            self.signals.done.emit(self.callback, self.operation(self.signals.progress.emit))
        except Exception as error:
            # No traceback or saved diagnostics containing personal paths.
            message = str(error).replace(str(Path.home()), "[user]")
            self.signals.failed.emit(message or "The operation could not be completed.")


class MainWindow(ThemedWindow):
    def __init__(self, preferences=None, player=None):
        super().__init__()
        self.preferences = preferences or AppearanceSettings()
        self.document: BarsDocument | None = None
        self.busy = self.dirty = False
        self.preview: Preview | None = None
        self.pending_play = False
        self.current_preview_key = None
        self.preview_cache = tempfile.TemporaryDirectory(prefix="splatoon-audio-preview-")
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.jobs = set()
        self.player = player or PreviewPlayer(self)
        self.audio = self.player.output
        self.player.positionChanged.connect(self.position_changed)
        self.player.playbackStateChanged.connect(self.playback_changed)
        self.player.errorOccurred.connect(self.playback_error)
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1120, 740)
        self.resize(1460, 920)
        self.setAcceptDrops(True)
        self._build_shortcuts()
        self._build_ui()
        self.set_theme(self.preferences.theme, save=False)
        self.set_busy(False)
        self.log("Ready. Open an audio file, or drop one anywhere in this window.")

    def set_theme(self, name, save=True):
        self.theme_name = apply_theme(QApplication.instance(), name)
        self.theme_actions[self.theme_name].setChecked(True)
        palette = active_palette()
        self.playback_changed(self.player.playbackState())
        self.restart_button.setIcon(playback_icon("restart", palette.text))
        row_icon = playback_icon("play", palette.accent)
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setIcon(row_icon)
            self.table.item(row, 0).setForeground(QColor(palette.accent))
            self.table.item(row, 5).setForeground(QColor(palette.text))
        self.wave.update()
        self.titlebar.update()
        if save:
            try:
                self.preferences.save_theme(self.theme_name)
            except OSError:
                QMessageBox.warning(self, APP_NAME, "The theme changed, but its preference could not be saved.")

    def _build_shortcuts(self):
        # Keyboard commands remain available without a native File/Playback/Help bar.
        action = QAction("Open audio file…", self)
        action.setShortcut(QKeySequence.StandardKey.Open)
        action.triggered.connect(self.open_dialog)
        self.addAction(action)
        action = QAction("Save as…", self)
        action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        action.triggered.connect(self.save_as)
        self.addAction(action)
        self.play_action = QAction("Play / pause", self)
        self.play_action.setShortcut(QKeySequence("Space"))
        self.play_action.triggered.connect(self.toggle_play)
        self.addAction(self.play_action)
        replay = QAction("Replay", self)
        replay.setShortcut(QKeySequence("Ctrl+R"))
        replay.triggered.connect(self.replay)
        self.addAction(replay)
        about = QAction("About", self)
        about.setShortcut(QKeySequence("F1"))
        about.triggered.connect(self.about)
        self.addAction(about)

    def _build_ui(self):
        root = Backdrop()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 8, 16, 12)
        layout.setSpacing(14)
        header = QHBoxLayout()
        title = QVBoxLayout()
        title.setSpacing(3)
        title.addWidget(label("SPLATOON AUDIO CONVERTER", "Brand"))
        title.addWidget(label("Extract WAVs, replace audio tracks or preview sounds.", "Muted"))
        header.addLayout(title)
        header.addStretch()
        self.settings_button = button("Settings", lambda: None, "Link")
        self.theme_menu = QMenu(self.settings_button)
        self.theme_menu.addSection("Application theme")
        self.theme_actions = {}
        group = QActionGroup(self.theme_menu)
        group.setExclusive(True)
        for name in PALETTES:
            action = self.theme_menu.addAction(name)
            action.setCheckable(True)
            group.addAction(action)
            action.triggered.connect(lambda checked=False, name=name: self.set_theme(name))
            self.theme_actions[name] = action
        self.settings_button.setMenu(self.theme_menu)
        header.addWidget(self.settings_button)
        self.update_button = button("Check for Updates", self.check_updates, "Primary")
        self.update_button.setToolTip("Check this app's latest GitHub release")
        header.addWidget(self.update_button)
        self.github_button = button("GitHub", lambda: QDesktopServices.openUrl(QUrl(updates.REPOSITORY_URL)), "Link")
        self.github_button.setToolTip("Source code, downloads and issue reports")
        header.addWidget(self.github_button)
        layout.addLayout(header)

        horizontal = QSplitter(Qt.Orientation.Horizontal)
        horizontal.setChildrenCollapsible(False)
        horizontal.addWidget(self._build_left())
        horizontal.addWidget(self._build_center())
        horizontal.addWidget(self._build_right())
        horizontal.setStretchFactor(0, 0)
        horizontal.setStretchFactor(1, 1)
        horizontal.setStretchFactor(2, 0)
        horizontal.setSizes([270, 820, 310])
        layout.addWidget(horizontal, 1)
        self.setCentralWidget(root)
        self.status = label("●  Ready", "Muted")
        self.statusBar().addWidget(self.status, 1)
        self.statusBar().addPermanentWidget(label("LOCAL FILES  ·  NO UPLOADS", "Tiny"))

    def _build_left(self):
        container = QWidget()
        container.setMinimumWidth(264)
        column = QVBoxLayout(container)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(12)
        archive = Panel("ARCHIVE")
        self.open_button = button("Open audio file…", self.open_dialog, "Primary")
        archive.body.addWidget(self.open_button)
        archive.body.addWidget(label("or drag a file into the window", "Tiny", True))
        self.filename = label("No file open", wrap=True)
        self.filename.setStyleSheet("font-weight:700; padding-top: 12px;")
        archive.body.addWidget(self.filename)
        self.archive_format = label("BARS · BWAV · BFSTM", "Muted")
        archive.body.addWidget(self.archive_format)
        self.archive_info = label("Compressed .zs files are supported too.", "Tiny", True)
        archive.body.addWidget(self.archive_info)
        column.addWidget(archive)

        export = Panel("EXTRACT & SAVE")
        self.extract_selected_button = button("Extract selected WAVs", self.extract_selected)
        self.extract_selected_button.setStyleSheet("font-size: 11px;")
        self.extract_all_button = button("Extract all WAVs", self.extract_all)
        self.save_button = button("Save as .bars.zs", self.save_as, "Primary")
        self.replacement_count = label("No replacements queued", "Tiny", True)
        for w in (self.extract_selected_button, self.extract_all_button, self.replacement_count, self.save_button):
            export.body.addWidget(w)
        column.addWidget(export)

        tips = Panel("QUICK GUIDE")
        tips.body.addWidget(label("1. Open an audio file\n2. Select a track to listen to\n3. Choose a replacement .wav file\n4. Save as a new file.", "Muted", True))
        tips.body.addWidget(label("Your original files are not affected.", "Tiny", True))
        column.addWidget(tips)
        column.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border:none; }")
        scroll.setMinimumWidth(264)
        scroll.setMaximumWidth(320)
        scroll.setWidget(container)
        return scroll

    def _build_center(self):
        vertical = QSplitter(Qt.Orientation.Vertical)
        vertical.setChildrenCollapsible(False)
        preview = Panel("")
        row = QHBoxLayout()
        row.addWidget(label("SOUND PREVIEW", "Section"))
        row.addStretch()
        self.source_combo = QComboBox()
        self.source_combo.addItems(["Original sound", "Replacement WAV"])
        self.source_combo.setFixedWidth(220)
        self.source_combo.currentIndexChanged.connect(self.preview_source_changed)
        row.addWidget(self.source_combo)
        preview.body.addLayout(row)
        self.track_title = label("Listen before you replace.", "TrackTitle")
        preview.body.addWidget(self.track_title)
        self.wave = Waveform()
        self.wave.seek.connect(self.seek)
        preview.body.addWidget(self.wave, 1)
        transport = QHBoxLayout()
        self.play_button = button("", self.toggle_play, "Transport")
        self.play_button.setIcon(playback_icon())
        self.play_button.setAccessibleName("Play or pause the selected sound")
        self.restart_button = button("", self.replay, "Restart")
        self.restart_button.setIcon(playback_icon("restart", active_palette().text))
        self.restart_button.setAccessibleName("Replay the selected track from the beginning")
        self.restart_button.setToolTip("Replay from the beginning (Ctrl+R)")
        self.time_label = label("00:00.00 / 00:00.00", "Muted")
        self.time_label.setMinimumWidth(153)
        transport.addWidget(self.play_button)
        transport.addWidget(self.restart_button)
        transport.addWidget(self.time_label)
        transport.addStretch()
        transport.addWidget(label("VOLUME", "Tiny"))
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 300)
        self.volume.setValue(100)
        self.volume.setFixedWidth(105)
        self.volume.valueChanged.connect(self.change_volume)
        self.volume.setAccessibleName("Preview volume, from zero to three hundred percent")
        self.volume.setToolTip("Preview only. Boost above 100% can distort loud sounds; exports are unchanged.")
        self.volume_label = label("100%", "Tiny")
        self.volume_label.setMinimumWidth(39)
        transport.addWidget(self.volume)
        transport.addWidget(self.volume_label)
        preview.body.addLayout(transport)
        vertical.addWidget(preview)

        library = Panel("")
        row = QHBoxLayout()
        row.addWidget(label("AUDIO TRACKS", "Section"))
        self.track_count = label("0 tracks", "Tiny")
        row.addWidget(self.track_count)
        row.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search sounds…")
        self.search.setMaximumWidth(260)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter_tracks)
        row.addWidget(self.search)
        library.body.addLayout(row)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["", "TRACK NAME", "DURATION", "FORMAT", "PLAYBACK", "STATUS"])
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(35)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for index, width in ((0, 33), (2, 97), (3, 112), (4, 96), (5, 98)):
            self.table.setColumnWidth(index, width)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        self.table.cellClicked.connect(self.track_clicked)
        library.body.addWidget(self.table, 1)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        library.body.addWidget(self.progress)
        vertical.addWidget(library)

        activity = Panel("ACTIVITY")
        self.activity = QPlainTextEdit()
        self.activity.setReadOnly(True)
        self.activity.setMaximumBlockCount(150)
        self.activity.setMinimumHeight(40)
        activity.body.addWidget(self.activity)
        vertical.addWidget(activity)
        vertical.setStretchFactor(0, 3)
        vertical.setStretchFactor(1, 4)
        vertical.setStretchFactor(2, 1)
        vertical.setSizes([310, 350, 120])
        return vertical

    def _build_right(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border:none; }")
        scroll.viewport().setAutoFillBackground(False)
        scroll.setMinimumWidth(260)
        scroll.setMaximumWidth(350)
        container = QWidget()
        column = QVBoxLayout(container)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(12)
        info = Panel("TRACK DETAILS")
        self.inspector_name = label("No sound selected", wrap=True)
        self.inspector_name.setStyleSheet("font-size: 14px; font-weight: 700;")
        info.body.addWidget(self.inspector_name)
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)
        self.values = {}
        for row, text in enumerate(("Duration", "Sample rate", "Channels", "Encoding", "Playback")):
            grid.addWidget(label(text, "Muted"), row, 0)
            value = label("—")
            self.values[text] = value
            grid.addWidget(value, row, 1)
        info.body.addLayout(grid)
        column.addWidget(info)

        replace = Panel("REPLACEMENT")
        self.replacement_label = label("Keep original audio", "Muted", True)
        self.replace_button = button("Choose WAV…", self.assign_replacement)
        self.clear_button = button("Remove replacement", self.clear_replacement)
        replace.body.addWidget(self.replacement_label)
        replace.body.addWidget(self.replace_button)
        replace.body.addWidget(self.clear_button)
        column.addWidget(replace)

        volume = Panel("AUDIO LEVELS")
        self.peak_value = label("—")
        self.rms_value = label("—")
        grid = QGridLayout()
        grid.addWidget(label("Peak", "Muted"), 0, 0)
        grid.addWidget(self.peak_value, 0, 1)
        grid.addWidget(label("Average", "Muted"), 1, 0)
        grid.addWidget(self.rms_value, 1, 1)
        volume.body.addLayout(grid)
        volume.body.addWidget(label("0 dBFS is the maximum. More negative numbers are quieter. These readings do not change your audio.", "Tiny", True))
        column.addWidget(volume)
        column.addStretch()
        scroll.setWidget(container)
        return scroll

    def log(self, text):
        self.activity.appendPlainText(f"{time.strftime('%H:%M:%S')}  {text}")

    def selected(self) -> list[Track]:
        if not self.document:
            return []
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        return [self.document.tracks[row] for row in rows if not self.table.isRowHidden(row)]

    def current(self) -> Track | None:
        selected = self.selected()
        return selected[0] if len(selected) == 1 else None

    def can_replace(self, track):
        return track is not None and track.codec != -1 and track.channels in (1, 2)

    def extension(self):
        if not self.document:
            return ".bars.zs"
        if self.document.is_stream:
            return ".bfstm.zs" if self.document.was_compressed else ".bfstm"
        if self.document.is_bwav:
            return ".bwav.zs" if self.document.was_compressed else ".bwav"
        return ".bars.zs"

    def normalized_name(self, name):
        if self.document.is_stream:
            return bfstm_name(name, self.document.was_compressed)
        if self.document.is_bwav:
            return bwav_name(name, self.document.was_compressed)
        return bars_zs_name(name)

    def set_busy(self, busy, message="Ready"):
        self.busy = busy
        self.status.setText(("◌  " if busy else "●  ") + message)
        self.progress.setRange(0, 0 if busy else 1)
        self.progress.setValue(0)
        track, document = self.current(), self.document
        self.open_button.setEnabled(not busy)
        self.update_button.setEnabled(not busy)
        self.extract_all_button.setEnabled(bool(document) and not busy)
        self.extract_selected_button.setEnabled(bool(self.selected()) and not busy)
        writable = document and all(self.can_replace(t) for t in document.tracks)
        self.save_button.setEnabled(bool(writable) and not busy)
        self.save_button.setText(f"Save as {self.extension()}")
        self.replace_button.setEnabled(self.can_replace(track) and not busy)
        self.clear_button.setEnabled(bool(track and document and track.name in document.replacements) and not busy)
        self.source_combo.setEnabled(bool(track) and not busy)
        self.play_button.setEnabled(bool(track) and not busy)
        self.restart_button.setEnabled(bool(track) and not busy)
        self.play_action.setEnabled(bool(track) and not busy)
        self.search.setEnabled(bool(document))

    def run_job(self, message, operation, callback):
        if self.busy:
            return
        self.set_busy(True, message)
        job = Job(operation, callback)
        self.jobs.add(job)
        job.signals.done.connect(self.job_done)
        job.signals.failed.connect(self.job_failed)
        job.signals.progress.connect(self.job_progress)
        self.pool.start(job)

    @Slot(str)
    def job_progress(self, text):
        self.status.setText("◌  " + text)

    @Slot(object, object)
    def job_done(self, callback, result):
        self.set_busy(False)
        self.jobs.clear()
        callback(result)

    @Slot(str)
    def job_failed(self, text):
        self.pending_play = False
        self.set_busy(False, "Could not complete the operation")
        self.jobs.clear()
        self.log(text)
        QMessageBox.warning(self, APP_NAME, text)

    def confirm_discard(self):
        return not self.dirty or QMessageBox.question(
            self, "Unsaved replacements", "Discard your unsaved replacement choices?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel) == QMessageBox.StandardButton.Discard

    def open_dialog(self):
        if self.busy:
            return
        filename, _ = QFileDialog.getOpenFileName(self, "Open a Splatoon audio file", "", FILTERS)
        if filename:
            self.open_path(Path(filename))

    def open_path(self, path: Path):
        if self.busy or not self.confirm_discard():
            return
        self.stop()
        self.run_job("Opening the audio file…", lambda _: BarsDocument(path), self.loaded)

    def loaded(self, document):
        self.player.setSource(QUrl())
        self.preview_cache.cleanup()
        self.preview_cache = tempfile.TemporaryDirectory(prefix="splatoon-audio-preview-")
        self.document, self.dirty = document, False
        self.preview = self.current_preview_key = None
        self.filename.setText(document.path.name)
        kind = "BWAV sound" if document.is_bwav else "BFSTM music" if document.is_stream else "BARS archive"
        self.archive_format.setText(kind + (" · compressed" if document.was_compressed else ""))
        self.archive_info.setText(f"{len(document.tracks)} tracks  ·  {len(document.bars) / (1024 * 1024):.2f} MB unpacked")
        self.table.blockSignals(True)
        self.table.setRowCount(len(document.tracks))
        for row, track in enumerate(document.tracks):
            fields = ("", track.name, clock(track.duration),
                      f"{track.sample_rate // 1000} kHz · {track.channels}ch",
                      "Loops" if track.loop_end >= 0 else "Once", "Original")
            for col, value in enumerate(fields):
                item = QTableWidgetItem(value)
                if col in (0, 2):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 0:
                    item.setIcon(playback_icon("play", active_palette().accent))
                    item.setForeground(QColor(active_palette().accent))
                    item.setToolTip("Preview this track")
                self.table.setItem(row, col, item)
        self.table.blockSignals(False)
        self.search.clear()
        self.filter_tracks("")
        self.replacements_changed()
        self.log(f"Opened {document.path.name}. Found {len(document.tracks)} sounds.")
        self.set_busy(False)
        if document.tracks:
            self.table.selectRow(0)

    def filter_tracks(self, text):
        if self.document:
            for row, track in enumerate(self.document.tracks):
                self.table.setRowHidden(row, text.casefold() not in track.name.casefold())
            visible = sum(not self.table.isRowHidden(i) for i in range(self.table.rowCount()))
            self.track_count.setText(f"{visible} / {len(self.document.tracks)}")
        self.selection_changed()

    def selection_changed(self):
        track = self.current()
        if not track:
            self.inspector_name.setText("Select one sound" if self.selected() else "No sound selected")
            for value in self.values.values():
                value.setText("—")
            if not self.busy:
                self.stop()
                self.wave.clear()
                self.preview = self.current_preview_key = None
                self.time_label.setText("00:00.00 / 00:00.00")
                self.peak_value.setText("—")
                self.rms_value.setText("—")
            self.set_busy(self.busy)
            return
        self.track_title.setText(track.name)
        self.inspector_name.setText(track.name)
        self.values["Duration"].setText(clock(track.duration))
        self.values["Sample rate"].setText(f"{track.sample_rate:,} Hz")
        self.values["Channels"].setText("Mono" if track.channels == 1 else "Stereo" if track.channels == 2 else str(track.channels))
        self.values["Encoding"].setText("Nintendo stream" if track.codec < 0 else "DSP-ADPCM" if track.codec == 1 else "PCM16")
        self.values["Playback"].setText("Loops" if track.loop_end >= 0 else "Plays once")
        replacement = self.document.replacements.get(track.name)
        self.source_combo.model().item(1).setEnabled(bool(replacement))
        if not replacement and self.source_combo.currentIndex() == 1:
            self.source_combo.blockSignals(True)
            self.source_combo.setCurrentIndex(0)
            self.source_combo.blockSignals(False)
        self.replacement_label.setText(replacement.name if replacement else "Keep original audio")
        self.set_busy(self.busy)
        if not self.busy:
            self.ensure_preview()

    def preview_source_changed(self):
        self.current_preview_key = None
        if not self.busy:
            self.ensure_preview()

    def ensure_preview(self, play=False):
        track = self.current()
        if not track or self.busy:
            return
        document = self.document
        replacement = self.source_combo.currentIndex() == 1
        replacement_path = document.replacements.get(track.name) if replacement else None
        key = (id(document), track.index, str(replacement_path) if replacement_path else "original")
        if self.current_preview_key == key and self.preview:
            if play:
                self.player.play()
            return
        self.stop()
        self.pending_play = play
        self.wave.clear("Preparing waveform…")
        self.peak_value.setText("…")
        self.rms_value.setText("…")
        cache = Path(self.preview_cache.name)

        def done(preview):
            current = self.current()
            if self.document is not document or not current or current.index != track.index:
                self.pending_play = False
                self.ensure_preview()
                return
            self.preview, self.current_preview_key = preview, key
            self.wave.set_preview(preview)
            self.peak_value.setText(db(preview.peak_db))
            self.rms_value.setText(db(preview.average_db))
            self.player.setSource(QUrl.fromLocalFile(str(preview.path)))
            self.time_label.setText(f"00:00.00 / {clock(preview.duration)}")
            if self.pending_play:
                self.player.play()
            self.pending_play = False
        self.run_job("Preparing selected sound…", lambda _: prepare(document, track, cache, replacement), done)

    def change_volume(self, value):
        self.volume_label.setText(f"{value}%")
        self.audio.setVolume(value / 100)

    def replay(self):
        if self.busy or not self.current():
            return
        self.player.setPosition(0)
        self.ensure_preview(play=True)

    def toggle_play(self):
        if self.busy:
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.ensure_preview(play=True)

    def track_clicked(self, row, column):
        if column == 0:
            self.table.selectRow(row)
            if self.busy:
                self.pending_play = True
            else:
                self.ensure_preview(play=True)

    def stop(self):
        self.player.stop()
        self.pending_play = False

    def seek(self, fraction):
        if self.preview and not self.busy:
            self.player.setPosition(int(fraction * self.preview.duration * 1000))

    @Slot(int)
    def position_changed(self, milliseconds):
        if self.preview:
            self.wave.position = min(1.0, milliseconds / max(1, self.preview.duration * 1000))
            self.wave.update()
            self.time_label.setText(f"{clock(milliseconds / 1000)} / {clock(self.preview.duration)}")

    @Slot(QMediaPlayer.PlaybackState)
    def playback_changed(self, state):
        if hasattr(self, "play_button"):
            self.play_button.setIcon(playback_icon("pause" if state == QMediaPlayer.PlaybackState.PlayingState else "play"))

    def playback_error(self, error, message):
        if error != QMediaPlayer.Error.NoError and hasattr(self, "activity"):
            self.log("Audio playback could not start. Try another sound or check the output device.")

    def assign_replacement(self):
        track = self.current()
        if self.busy or not self.can_replace(track):
            return
        filename, _ = QFileDialog.getOpenFileName(self, "Choose a replacement WAV", "", "16-bit PCM WAV (*.wav)")
        if filename:
            self.assign_path(track, Path(filename))

    def assign_path(self, track, path):
        try:
            rate, pcm = read_pcm16(path)
            if len(pcm) == 0:
                raise ValueError("Choose a WAV with at least one sample.")
        except Exception:
            QMessageBox.warning(self, "Unsupported WAV", "Choose a mono or stereo, uncompressed 16-bit PCM WAV file.")
            return
        self.document.replacements[track.name] = path
        self.dirty = True
        self.table.item(track.index, 5).setText("Replaced")
        self.table.item(track.index, 5).setForeground(QColor(active_palette().accent))
        self.log(f"Queued {path.name} for {track.name} ({len(pcm) / rate:.2f} s).")
        self.replacements_changed()
        self.current_preview_key = None
        self.source_combo.blockSignals(True)
        self.source_combo.setCurrentIndex(1)
        self.source_combo.blockSignals(False)
        self.selection_changed()

    def clear_replacement(self):
        if self.busy or not self.document:
            return
        for track in self.selected():
            if self.document.replacements.pop(track.name, None):
                self.dirty = True
                self.table.item(track.index, 5).setText("Original")
        self.current_preview_key = None
        self.replacements_changed()
        self.selection_changed()

    def replacements_changed(self):
        count = len(self.document.replacements) if self.document else 0
        self.replacement_count.setText(f"{count} replacement{'s' if count != 1 else ''} queued")
        self.set_busy(self.busy)

    def extract_selected(self):
        self.extract_tracks(self.selected())

    def extract_all(self):
        if self.document:
            self.extract_tracks(self.document.tracks)

    def extract_tracks(self, tracks):
        if self.busy or not tracks:
            return
        folder = QFileDialog.getExistingDirectory(self, "Choose a folder for extracted WAVs")
        if not folder:
            return
        destination = Path(folder) / (bars_base_name(self.document.path.name) + "_WAV")
        if destination.exists() and any(destination.iterdir()):
            if QMessageBox.question(self, "Existing extraction", "This output folder already contains files. Replace matching WAV files?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
        document = self.document
        self.run_job("Extracting WAVs…", lambda _: document.extract(tracks, destination),
                     lambda _: self.log(f"Extracted {len(tracks)} WAV files. No manifest was created."))

    def save_as(self):
        if self.busy or not self.document or not all(self.can_replace(t) for t in self.document.tracks):
            return
        extension = self.extension()
        suggested = self.normalized_name(self.document.path.name)
        # Non-native dialog gives consistent multi-part suffix behavior on Windows.
        dialog = QFileDialog(self, f"Save as {extension}")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setNameFilter(f"Game audio (*{extension})")
        dialog.setDefaultSuffix(extension.lstrip("."))
        dialog.selectFile(suggested)
        if not dialog.exec():
            return
        chosen = Path(dialog.selectedFiles()[0])
        output = chosen.with_name(self.normalized_name(chosen.name))
        if output.resolve() == self.document.path.resolve():
            QMessageBox.warning(self, "Keep the original", "Choose another folder or filename. The original audio file is never overwritten.")
            return
        if output.exists() and output != chosen:
            if QMessageBox.question(self, "Replace output file?", f"Replace {output.name}?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
        document = self.document
        def done(result):
            self.dirty = False
            self.log(f"Saved {output.name}. Replaced {result['entries_replaced']} of {result['entries_total']} tracks.")
            self.status.setText("●  File saved. Original unchanged.")
        self.run_job("Saving game audio…", lambda progress: document.build(output, progress), done)

    def check_updates(self):
        def done(release):
            if not release:
                self.log("You have the latest published version.")
                QMessageBox.information(self, "Updates", "You have the latest published version.")
            elif QMessageBox.question(self, "Update available", f"{release.version} is available. Open its GitHub download page?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl(release.url))
        self.run_job("Checking GitHub Releases…", lambda _: updates.check(), done)

    def about(self):
        QMessageBox.information(self, APP_NAME,
            f"{APP_NAME}\nVersion {__version__}\n\nExtract WAVs, replace audio tracks or preview sounds.\n\n"
            "Visual layout inspired by HoianViewer by nvnprogram.\nThe interface is independently implemented; no viewer assets are included.\n\n"
            "Audio: NumPy, Zstandard and VGAudio. Interface/playback: Qt for Python.\n"
            "GitHub update checks are manual. Audio files are never uploaded.")

    def dragEnterEvent(self, event):
        if not self.busy and event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.open_path(Path(url.toLocalFile()))
                event.acceptProposedAction()
                break

    def closeEvent(self, event):
        if self.busy:
            QMessageBox.information(self, APP_NAME, "Please wait for the current operation to finish before closing.")
            event.ignore()
            return
        if not self.confirm_discard():
            event.ignore()
            return
        self.player.stop()
        self.player.setSource(QUrl())
        self.preview_cache.cleanup()
        event.accept()


def main():
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("file", nargs="?", type=Path)
    parser.add_argument("--snapshot", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("SplatoonAudioConverter")
    configure(app)
    window = MainWindow()
    if args.snapshot:
        if not args.file:
            parser.error("A file is required for --snapshot")
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.show()
    if args.file:
        QTimer.singleShot(100, lambda: window.open_path(args.file))
    if args.snapshot:
        deadline = time.monotonic() + 30
        timer = QTimer(window)
        def capture():
            if window.document and window.preview and not window.busy:
                args.snapshot.parent.mkdir(parents=True, exist_ok=True)
                success = window.grab().save(str(args.snapshot))
                timer.stop()
                window.close()
                app.exit(0 if success else 1)
            elif time.monotonic() > deadline:
                timer.stop()
                app.exit(1)
        timer.timeout.connect(capture)
        timer.start(100)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
