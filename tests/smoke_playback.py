"""Bounded, muted real-device check: live volume, pause, seek, EOF and replay."""
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

from PySide6.QtCore import Qt, QTimer
from PySide6.QtMultimedia import QMediaDevices, QMediaPlayer
from PySide6.QtWidgets import QApplication
from splatoon_audio_converter.fonts import configure
from splatoon_audio_converter.preferences import AppearanceSettings
from splatoon_audio_converter.ui import MainWindow
from fixtures import pcm_bwav


def main():
    app = QApplication([])
    if QMediaDevices.defaultAudioOutput().isNull():
        print("SKIP: no real output device; deterministic streaming and GUI tests cover this runner.")
        return
    configure(app, "Beige")
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "Playback_Check.bwav"
        path.write_bytes(pcm_bwav(seconds=2.5))
        window = MainWindow(AppearanceSettings(Path(folder) / "theme.ini"))
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        window.show()
        window.audio.setMuted(True)
        player = window.player
        state = {"phase": 0, "changes": 0, "worst": 0.0}
        errors = []
        timer = QTimer()
        timer.setInterval(10)

        def finish(code):
            timer.stop()
            player.stop()
            window.dirty = False
            window.close()
            app.exit(code)

        def tick():
            try:
                if state["phase"] == 0 and window.preview and not window.busy:
                    window.toggle_play()
                    assert player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                    reload.reset_mock(); stop.reset_mock()
                    state.update(phase=1, start=time.monotonic(), sink=player._sink)
                elif state["phase"] == 1:
                    start = time.perf_counter()
                    window.volume.setValue((state["changes"] * 31) % 301)
                    state["worst"] = max(state["worst"], time.perf_counter() - start)
                    state["changes"] += 1
                    assert not window.busy and player._sink is state["sink"]
                    reload.assert_not_called(); stop.assert_not_called()
                    assert player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                    if time.monotonic() - state["start"] > 1.0:
                        assert player.position() >= 700
                        player.pause()
                        state.update(phase=2, position=player.position(), start=time.monotonic())
                elif state["phase"] == 2 and time.monotonic() - state["start"] > .15:
                    assert player.position() == state["position"]
                    window.volume.setValue(300)
                    assert player.playbackState() == QMediaPlayer.PlaybackState.PausedState
                    window.restart_button.click()
                    assert player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                    assert player.position() < 100
                    state["phase"] = 3
                elif state["phase"] == 3 and player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
                    window.restart_button.click()
                    assert player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                    assert player.position() < 100
                    print(f"PASS: {state['changes']} live volume changes without resets; slowest handler {state['worst'] * 1000:.2f} ms; pause, EOF and replay passed.")
                    finish(0)
            except Exception as error:
                errors.append(str(error) or type(error).__name__)
                finish(1)

        with patch.object(player, "setSource", wraps=player.setSource) as reload, patch.object(player, "stop", wraps=player.stop) as stop:
            timer.timeout.connect(tick)
            timer.start()
            QTimer.singleShot(50, lambda: window.open_path(path))
            QTimer.singleShot(12000, lambda: finish(2))
            code = app.exec()
        if code:
            raise RuntimeError("Playback check failed: " + (", ".join(errors) or "timeout"))


if __name__ == "__main__":
    main()
