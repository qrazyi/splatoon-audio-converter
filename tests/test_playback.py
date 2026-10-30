from pathlib import Path
import tempfile
import unittest
import time
import wave
from unittest.mock import patch

import numpy as np

from PySide6.QtCore import QCoreApplication, QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudio, QAudioFormat, QMediaPlayer
from fixtures import replacement_wav
from splatoon_audio_converter.playback import PreviewPlayer, _PlaybackEngine, preview_pcm


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
        self.format = format
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
            player = _PlaybackEngine(sink_factory=FakeSink)
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
            player = _PlaybackEngine(sink_factory=FakeSink)
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

    def test_audio_worker_keeps_feeding_when_gui_thread_is_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "preview.wav"
            replacement_wav(path, seconds=15)
            player = PreviewPlayer(sink_factory=FakeSink)
            try:
                player.setSource(QUrl.fromLocalFile(str(path)))
                player.play()
                deadline = time.monotonic() + 3
                while player.playbackState() != QMediaPlayer.PlaybackState.PlayingState and time.monotonic() < deadline:
                    self.app.processEvents()
                    time.sleep(.005)
                self.assertEqual(player.playbackState(), QMediaPlayer.PlaybackState.PlayingState)
                self.assertIsNot(player._engine.thread(), self.app.thread())
                written = len(player._engine._sink.device.data)
                # Intentionally do not dispatch any GUI events during this stall.
                time.sleep(.35)
                self.assertGreater(len(player._engine._sink.device.data), written)
                self.assertEqual(player._engine._sink.starts, 1)
                self.assertEqual(player._engine._sink.resets, 0)
            finally:
                player.shutdown()
            self.assertFalse(player._thread.isRunning())

    def test_multichannel_music_plays_first_stereo_pair_without_changing_file(self):
        for channels in (4, 6, 8, 10, 32):
            with self.subTest(channels=channels), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "music.wav"
                pcm = np.tile(np.arange(channels, dtype="<i2") * 1000, (1024, 1))
                with wave.open(str(path), "wb") as writer:
                    writer.setnchannels(channels)
                    writer.setsampwidth(2)
                    writer.setframerate(48000)
                    writer.writeframes(pcm.tobytes())
                original = path.read_bytes()
                player = _PlaybackEngine(sink_factory=FakeSink)
                try:
                    player.setSource(QUrl.fromLocalFile(str(path)))
                    player.play()
                    self.assertEqual(player._sink.format.channelCount(), 2)
                    self.assertEqual(bytes(player._sink.device.data), pcm[:, :2].tobytes())
                    self.assertEqual(player.playbackState(), QMediaPlayer.PlaybackState.PlayingState)
                finally:
                    player.setSource(QUrl())
                self.assertEqual(path.read_bytes(), original)
        self.assertEqual(preview_pcm(b"\x01\x00\x02\x00", 1), b"\x01\x00\x02\x00")

    def test_float_only_output_uses_float_pcm(self):
        class FloatDevice:
            def isNull(self): return False
            def isFormatSupported(self, format):
                return format.sampleFormat() == QAudioFormat.SampleFormat.Float

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "preview.wav"
            replacement_wav(path, channels=4)
            player = _PlaybackEngine()
            with patch("splatoon_audio_converter.playback.QMediaDevices.defaultAudioOutput", return_value=FloatDevice()), \
                 patch("splatoon_audio_converter.playback.QAudioSink", side_effect=lambda device, format, parent: FakeSink(format, parent)):
                try:
                    player.setSource(QUrl.fromLocalFile(str(path)))
                    player.play()
                    self.assertEqual(player._sink.format.sampleFormat(), QAudioFormat.SampleFormat.Float)
                    samples = np.frombuffer(player._sink.device.data, dtype="<f4").reshape(-1, 2)
                    self.assertEqual(len(samples), 512)
                    self.assertTrue(np.all(np.isfinite(samples)))
                    self.assertLessEqual(float(np.abs(samples).max()), 1)
                    self.assertGreater(float(np.abs(samples).max()), .1)
                finally:
                    player.setSource(QUrl())
