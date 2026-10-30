from pathlib import Path
import tempfile
import unittest

from PySide6.QtCore import QCoreApplication, QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudio, QMediaPlayer
from fixtures import replacement_wav
from splatoon_audio_converter.playback import PreviewPlayer


class FakeDevice:
    def __init__(self):
        self.data = bytearray()

    def write(self, data):
        self.data.extend(data)
        return len(data)


class FakeSink(QObject):
    stateChanged = Signal(QAudio.State)

    def __init__(self, format, parent):
        super().__init__(parent)
        self.starts = self.resets = 0
        self.elapsed = 0
        self._state = QAudio.State.StoppedState
        self.device = FakeDevice()

    def setBufferSize(self, size): pass
    def bytesFree(self): return 4096
    def processedUSecs(self): return self.elapsed
    def state(self): return self._state
    def error(self): return QAudio.Error.NoError

    def start(self):
        self.starts += 1
        self.elapsed = 0
        self._state = QAudio.State.ActiveState
        return self.device

    def reset(self):
        self.resets += 1
        self._state = QAudio.State.StoppedState
        self.stateChanged.emit(self._state)

    def suspend(self): self._state = QAudio.State.SuspendedState
    def resume(self): self._state = QAudio.State.ActiveState


class PlaybackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_rapid_volume_changes_do_not_reset_reload_seek_or_write_files(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "preview.wav"
            replacement_wav(path, seconds=10)
            original = path.read_bytes()
            player = PreviewPlayer(sink_factory=FakeSink)
            player.setSource(QUrl.fromLocalFile(str(path)))
            player.play()
            reader, sink = player._reader, player._sink
            for value in range(0, 301, 3):
                player.output.setVolume(value / 100)
                player._pump()
                self.assertIs(player._reader, reader)
                self.assertIs(player._sink, sink)
                self.assertEqual(sink.starts, 1)
                self.assertEqual(sink.resets, 0)
                self.assertEqual(player.playbackState(), QMediaPlayer.PlaybackState.PlayingState)
            player.setSource(QUrl())
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual([p.name for p in Path(folder).iterdir()], ["preview.wav"])

    def test_pause_seek_replay_and_end_of_media(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "preview.wav"
            replacement_wav(path, seconds=2)
            player = PreviewPlayer(sink_factory=FakeSink)
            player.setSource(QUrl.fromLocalFile(str(path)))
            player.play()
            player._sink.elapsed = 150000
            self.assertEqual(player.position(), 150)
            player.pause()
            player.output.setVolume(3)
            self.assertEqual(player.position(), 150)
            self.assertEqual(player.playbackState(), QMediaPlayer.PlaybackState.PausedState)
            player.setPosition(300)
            self.assertEqual(player.playbackState(), QMediaPlayer.PlaybackState.PausedState)
            self.assertEqual(player.position(), 300)
            player.play()
            player._eof, player._pending = True, b""
            player._sink_state(QAudio.State.IdleState)
            self.assertEqual(player.mediaStatus(), QMediaPlayer.MediaStatus.EndOfMedia)
            self.assertEqual(player.position(), 2000)
            player.play()
            self.assertEqual(player.playbackState(), QMediaPlayer.PlaybackState.PlayingState)
            self.assertEqual(player.position(), 0)
            player.setSource(QUrl())
