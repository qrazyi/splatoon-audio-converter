"""Muted real-device test including hidden windows and a blocked GUI thread."""
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
        print("SKIP: no real output device; deterministic worker and GUI tests cover this runner.")
        return
    configure(app, "Brown")
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "Playback_Check.bwav"
        path.write_bytes(pcm_bwav(seconds=3.5))
        window = MainWindow(AppearanceSettings(Path(folder) / "theme.ini"))
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        window.show()
        window.audio.setMuted(True)
        player = window.player
        state = {"phase": "open", "changes": 0, "worst": 0.0, "finished": False}
        errors = []
        timer = QTimer()
        timer.setInterval(10)

        def finish(code):
            if state["finished"]:
                return
            state["finished"] = True
            timer.stop()
            player.shutdown()
            window.dirty = False
            if not window.busy:
                window.close()
            app.exit(code)

        def tick():
            try:
                phase = state["phase"]
                if phase == "open" and window.preview and not window.busy:
                    window.toggle_play()
                    state["phase"] = "starting"
                elif phase == "starting" and player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                    reload.reset_mock(); stop.reset_mock()
                    state.update(phase="volume", start=time.monotonic())
                elif phase == "volume":
                    start = time.perf_counter()
                    window.volume.setValue((state["changes"] * 31) % 301)
                    state["worst"] = max(state["worst"], time.perf_counter() - start)
                    state["changes"] += 1
                    assert not window.busy
                    reload.assert_not_called(); stop.assert_not_called()
                    assert player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                    if time.monotonic() - state["start"] > 1.0:
                        assert player.position() >= 700
                        player.pause()
                        state["phase"] = "pausing"
                elif phase == "pausing" and player.playbackState() == QMediaPlayer.PlaybackState.PausedState:
                    state.update(phase="paused", position=player.position(), start=time.monotonic())
                elif phase == "paused" and time.monotonic() - state["start"] > .15:
                    assert abs(player.position() - state["position"]) <= 30
                    window.volume.setValue(300)
                    window.restart_button.click()
                    state["phase"] = "restarting"
                elif phase == "restarting" and player.playbackState() == QMediaPlayer.PlaybackState.PlayingState and player.position() < 150:
                    state.update(phase="cover", start=time.monotonic())
                elif phase == "cover" and time.monotonic() - state["start"] > .3:
                    window.hide()
                    before = player._engine.bytes_streamed
                    # Deliberately deny the UI an event loop for longer than the
                    # complete audio buffer while every app window is hidden.
                    time.sleep(.35)
                    assert player._engine.bytes_streamed > before, "Background audio stopped feeding with the GUI blocked"
                    assert player._engine.underruns == 0, "Audio buffer underrun during background/GUI-stall test"
                    window.show()
                    state["phase"] = "ending"
                elif phase == "ending" and player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
                    window.restart_button.click()
                    state["phase"] = "final replay"
                elif phase == "final replay" and player.playbackState() == QMediaPlayer.PlaybackState.PlayingState and player.position() < 150:
                    assert player._engine.underruns == 0
                    print(f"PASS: {state['changes']} live volume changes; slowest handler {state['worst'] * 1000:.2f} ms; hidden-window playback and 350 ms GUI stall without underruns; pause/EOF/replay passed.")
                    finish(0)
            except Exception as error:
                errors.append(str(error) or type(error).__name__)
                finish(1)

        with patch.object(player, "setSource", wraps=player.setSource) as reload, patch.object(player, "stop", wraps=player.stop) as stop:
            timer.timeout.connect(tick)
            timer.start()
            QTimer.singleShot(50, lambda: window.open_path(path))
            QTimer.singleShot(14000, lambda: finish(2))
            code = app.exec()
        if code:
            raise RuntimeError("Playback check failed: " + (", ".join(errors) or "timeout"))


if __name__ == "__main__":
    main()
