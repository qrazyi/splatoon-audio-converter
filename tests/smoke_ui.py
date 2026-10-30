"""Hidden-window Qt integration/rendering test; no game assets or UI automation."""
import os
import sys
import tempfile
import time
from unittest.mock import patch
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "windows" if sys.platform == "win32" else "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, QCoreApplication, QEvent
from PySide6.QtMultimedia import QMediaPlayer
from splatoon_audio_converter.ui import MainWindow
from splatoon_audio_converter import updates
from splatoon_audio_converter.fonts import configure
from fixtures import bars, replacement_wav


def wait_ready(app, window, timeout=30):
    deadline = time.monotonic() + timeout
    while window.busy and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    app.processEvents()
    assert not window.busy, "Background operation timed out"


def main():
    app = QApplication([])
    configure(app)
    window = MainWindow()
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
        assert window.update_button.text() == "Check for Updates"
        assert not window.findChildren(__import__("PySide6.QtWidgets", fromlist=["QMenuBar"]).QMenuBar)
        assert window.volume.maximum() == 200
        assert window.volume.value() == 100
        window.audio.setMuted(True)
        window.toggle_play()
        deadline = time.monotonic() + 5
        while window.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        assert window.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState, "Preview playback did not start"
        window.player.setPosition(160)
        window.player.pause()
        window.restart_button.click()
        app.processEvents()
        assert window.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState, "Replay must resume playback, not leave it paused"
        assert window.player.position() < 100, "Replay did not seek back to the start"
        window.stop()
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
        assert window.peak_value.text().endswith("dBFS")
        window.search.setText("Cancel")
        assert sum(not window.table.isRowHidden(i) for i in range(10)) == 1
        window.search.clear()
        window.table.selectRow(2)
        wait_ready(app, window)
        assert window.wave.peaks is not None
        window.volume.setValue(200)
        window.volume_timer.stop()
        window.refresh_volume_preview()
        wait_ready(app, window)
        assert window.preview.gain == 200
        assert window.preview.playback_path != window.preview.path
        window.volume.setValue(75)
        window.volume_timer.stop()
        window.refresh_volume_preview()
        wait_ready(app, window)
        assert window.preview.gain == 100
        assert abs(window.audio.volume() - .75) < .001
        assert window.preview.playback_path == window.preview.path
        with patch.object(updates, "check", return_value=None) as check, patch("splatoon_audio_converter.ui.QMessageBox.information") as notice:
            window.update_button.click()
            wait_ready(app, window)
            check.assert_called_once()
            notice.assert_called_once()
            assert window.update_button.isEnabled()
        app.processEvents()
        assert window.grab().save(str(output / "workbench.png"))
        window.dirty = False
        window.close()
        window.pool.waitForDone()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
    print("PASS: open, duration, waveform, playback, immediate replay, 200% boost, selection, replacement, levels, filter and screenshots")


if __name__ == "__main__":
    main()
