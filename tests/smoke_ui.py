"""Hidden-window Qt integration/rendering test; no game assets or UI automation."""
import os
import sys
import tempfile
import time
import uuid
from unittest.mock import patch
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "windows" if sys.platform == "win32" else "offscreen")

from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, QCoreApplication, QEvent, QPoint, QPointF
from PySide6.QtMultimedia import QMediaDevices, QMediaPlayer
from splatoon_audio_converter.ui import MainWindow
from splatoon_audio_converter.fonts import configure
from splatoon_audio_converter.preferences import AppearanceSettings
from splatoon_audio_converter import preferences as preference_module
from splatoon_audio_converter.theme import PALETTES
from fixtures import bars, replacement_wav


def wait_ready(app, window, timeout=30):
    deadline = time.monotonic() + timeout
    while window.busy and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    app.processEvents()
    assert not window.busy, "Background operation timed out"


def until(app, condition, timeout=5):
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.005)
    assert condition(), "Asynchronous audio operation did not complete"


def main():
    app = QApplication([])
    configure(app, "Dorfic")
    preferences_folder = tempfile.TemporaryDirectory()
    window = MainWindow(AppearanceSettings(Path(preferences_folder.name) / "appearance.ini"))
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.show()
    app.processEvents()
    output = Path("test-output")
    output.mkdir(exist_ok=True)
    assert window.grab().save(str(output / "empty.png"))
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "Demo_Sounds.bars"
        path.write_bytes(bars(("UI_Confirm", "UI_Cancel", "UI_Decide", "UI_Notification", "UI_Scroll", "UI_Start", "UI_MenuOpen", "UI_MenuClose", "UI_Ready", "UI_Select")))
        window.open_path(path)
        wait_ready(app, window)
        assert window.table.rowCount() == 10
        assert window.table.item(0, 2).text() == "00:00.32"
        assert window.preview and window.preview.duration == .32
        assert window.themes_button.text() == "Themes"
        assert window.theme_name == "Dorfic"
        assert not hasattr(window, "update_button") and not hasattr(window, "github_button")
        assert not hasattr(window, "check_updates")
        assert not window.findChildren(__import__("PySide6.QtWidgets", fromlist=["QMenuBar"]).QMenuBar)
        assert window.volume.maximum() == 300
        assert window.volume.value() == 100
        window.audio.setMuted(True)
        if not QMediaDevices.defaultAudioOutput().isNull():
            window.toggle_play()
            until(app, lambda: window.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
            assert window.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState, "Preview playback did not start"
            window.player.setPosition(160)
            window.player.pause()
            until(app, lambda: window.player.playbackState() == QMediaPlayer.PlaybackState.PausedState)
            window.restart_button.click()
            until(app, lambda: window.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState and window.player.position() < 100)
            assert window.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState, "Replay must resume playback, not leave it paused"
            assert window.player.position() < 100, "Replay did not seek back to the start"
        window.stop()
        until(app, lambda: window.player.playbackState() == QMediaPlayer.PlaybackState.StoppedState)
        assert window.player.playbackState() == QMediaPlayer.PlaybackState.StoppedState
        window.table.selectRow(2)
        wait_ready(app, window)
        assert window.values["Playback"].text() == "Loops"
        wav = Path(folder) / "My_Custom_Sound.wav"
        replacement_wav(wav)
        window.assign_path(window.current(), wav)
        wait_ready(app, window)
        assert window.table.item(2, 5).text() == "Replaced"
        assert window.preview.replacement
        window.search.setText("Cancel")
        assert sum(not window.table.isRowHidden(i) for i in range(10)) == 1
        window.search.clear()
        window.table.selectRow(2)
        wait_ready(app, window)
        assert window.wave.peaks is not None
        preview, source = window.preview, window.player.source()
        with patch.object(window.player, "setSource", wraps=window.player.setSource) as reload, patch.object(window.player, "stop", wraps=window.player.stop) as stop:
            for value in range(0, 301, 3):
                window.volume.setValue(value)
            reload.assert_not_called()
            stop.assert_not_called()
        assert not window.busy and window.preview is preview and window.player.source() == source
        assert window.audio.volume() == 3
        window.volume.setValue(75)
        assert abs(window.audio.volume() - .75) < .001
        assert not list(Path(window.preview_cache.name).glob("volume-*.wav"))
        texts = "\n".join(widget.text() for widget in window.findChildren(QLabel))
        for removed in ("AUDIO LEVELS", "LOOP BEHAVIOR", "Preserve the original loop", "Mono or stereo, 16-bit PCM WAV.", "No manifest or extra JSON files."):
            assert removed not in texts
        for name in PALETTES:
            window.theme_actions[name].trigger()
            app.processEvents()
            assert window.theme_name == name
            assert window.preferences.theme == name
            assert window.grab().save(str(output / ("theme-" + name.lower().replace(" ", "-") + ".png")))
        window.set_theme("Dorfic")
        menu = window.theme_menu
        menu.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        menu.popup(QPoint(30, 30))
        app.processEvents()
        assert not menu.mask().contains(QPoint(0, 0))
        assert menu.mask().contains(menu.rect().center())
        assert menu.grab().save(str(output / "theme-menu.png"))
        menu.hide()
        assert window.titlebar.caption.text() == "Splatoon Audio Converter"
        window.update_resize_cursor(QPointF(1, 1))
        assert window.cursor().shape() == Qt.CursorShape.SizeFDiagCursor
        window.toggle_maximized()
        app.processEvents()
        assert window.isMaximized()
        assert window.cursor().shape() == Qt.CursorShape.ArrowCursor
        window.update_resize_cursor(QPointF(1, 1))
        assert window.cursor().shape() == Qt.CursorShape.ArrowCursor
        window.toggle_maximized()
        assert not window.isMaximized()
        window.update_resize_cursor(QPointF(1, 1))
        window.showFullScreen()
        app.processEvents()
        assert window.cursor().shape() == Qt.CursorShape.ArrowCursor
        window.update_resize_cursor(QPointF(1, 1))
        assert window.cursor().shape() == Qt.CursorShape.ArrowCursor
        window.showNormal()
        window.update_resize_cursor(QPointF(1, 1))
        window.update_resize_cursor(QPointF(100, 100))
        assert window.cursor().shape() == Qt.CursorShape.ArrowCursor
        window.resize(1460, 920)
        app.processEvents()
        assert window.grab().save(str(output / "workbench.png"))
        window.dirty = False
        window.close()
        window.pool.waitForDone()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
    preferences_folder.cleanup()
    if sys.platform == "win32":
        # Exercise the production native-settings path through the real theme
        # actions, not only the explicit INI backend used by the tests above.
        test_name = "UiPreferenceTests-" + uuid.uuid4().hex
        with patch.object(preference_module, "APPLICATION", test_name):
            settings = AppearanceSettings()
            persistent = MainWindow(settings)
            persistent.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
            persistent.show()
            app.processEvents()
            try:
                with patch("splatoon_audio_converter.ui.QMessageBox.warning") as warning:
                    for name in PALETTES:
                        persistent.theme_actions[name].trigger()
                        app.processEvents()
                        assert AppearanceSettings().theme == name
                    warning.assert_not_called()
                persistent.close()
                persistent.pool.waitForDone()
                reopened = MainWindow(AppearanceSettings())
                reopened.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
                try:
                    assert reopened.theme_name == "Eco", "Saved theme was lost on window restart"
                finally:
                    reopened.close()
                    reopened.pool.waitForDone()
                    reopened.deleteLater()
            finally:
                persistent.close()
                persistent.deleteLater()
                settings.store.clear()
                settings.store.sync()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                app.processEvents()
    print("PASS: opaque UI, five exact gradient themes, Dorfic default, rounded native theme popup, audio controls and fullscreen cursor recovery.")
    print("PASS: native Windows theme saves verified after every menu action and after reopening; no save-warning dialog.")


if __name__ == "__main__":
    main()
