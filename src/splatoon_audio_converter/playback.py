"""Dedicated-thread PCM playback, independent of UI focus and repaint timing."""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
from PySide6.QtCore import QCoreApplication, QMetaObject, QObject, QThread, QTimer, QUrl, Qt, Signal, Slot
from PySide6.QtMultimedia import QAudio, QAudioFormat, QAudioSink, QMediaDevices, QMediaPlayer


def amplify(pcm: bytes, channels: int, current: float, target: float, rate: int):
    """Apply gain with an 8 ms ramp to avoid clicks, then saturate, never wrap."""
    frames = len(pcm) // (channels * 2)
    if not frames:
        return pcm, current
    if current == target == 1:
        return pcm, target
    samples = np.frombuffer(pcm, dtype="<i2").reshape(-1, channels).astype(np.float32)
    ramp = current + (target - current) * np.minimum(
        (np.arange(frames, dtype=np.float32) + 1) / max(1, round(rate * .008)), 1)
    samples *= ramp[:, None]
    return np.clip(np.rint(samples), -32768, 32767).astype("<i2").tobytes(), float(ramp[-1])


def preview_pcm(pcm: bytes, channels: int) -> bytes:
    """Nintendo music stores stereo layers, not a speaker-surround mix.

    Audition the first stereo pair rather than sending 4–32 channels to an
    ordinary output device or stacking alternate music layers on top of it.
    This changes only the playback buffer, never the source or extracted WAV.
    """
    if channels <= 2:
        return pcm
    return np.frombuffer(pcm, dtype="<i2").reshape(-1, channels)[:, :2].copy().tobytes()


class PreviewOutput:
    def __init__(self):
        self._volume = 1.0
        self._muted = False

    def setVolume(self, value):
        self._volume = max(0.0, min(3.0, float(value)))

    def volume(self):
        return self._volume

    def setMuted(self, value):
        self._muted = bool(value)

    def isMuted(self):
        return self._muted


class _PlaybackEngine(QObject):
    positionChanged = Signal(int)
    playbackStateChanged = Signal(QMediaPlayer.PlaybackState)
    mediaStatusChanged = Signal(QMediaPlayer.MediaStatus)
    errorOccurred = Signal(QMediaPlayer.Error, str)
    durationChanged = Signal(int)

    def __init__(self, parent=None, sink_factory=None):
        super().__init__(parent)
        self.output = PreviewOutput()
        self._sink_factory = sink_factory
        self._source = QUrl()
        self._reader = None
        self._sink = self._device = None
        self._state = QMediaPlayer.PlaybackState.StoppedState
        self._status = QMediaPlayer.MediaStatus.NoMedia
        self._base_frame = self._last_position = 0
        self._pending = b""
        self._eof = self._resetting = False
        self._gain = 1.0
        self._sample_format = QAudioFormat.SampleFormat.Int16
        self.underruns = 0
        self.bytes_streamed = 0
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(5)
        self._timer.timeout.connect(self._pump)

    @Slot(str, object)
    def command(self, name, value):
        if name == "source":
            self.setSource(value)
        elif name == "position":
            self.setPosition(value)
        elif name in ("play", "pause", "stop"):
            getattr(self, name)()

    @Slot()
    def clear_source(self):
        self.setSource(QUrl())

    def _set_state(self, state):
        if self._state != state:
            self._state = state
            self.playbackStateChanged.emit(state)

    def _set_status(self, status):
        if self._status != status:
            self._status = status
            self.mediaStatusChanged.emit(status)

    def playbackState(self):
        return self._state

    def mediaStatus(self):
        return self._status

    def source(self):
        return self._source

    def duration(self):
        return round(self._reader.getnframes() * 1000 / self._reader.getframerate()) if self._reader else 0

    def position(self):
        if not self._reader:
            return 0
        elapsed = self._sink.processedUSecs() // 1000 if self._sink and self._device else 0
        return min(self.duration(), round(self._base_frame * 1000 / self._reader.getframerate()) + elapsed)

    def _reset_sink(self):
        self._timer.stop()
        self._resetting = True
        if self._sink:
            self._sink.reset()  # Discard queued data, do not wait for a drain.
        self._resetting = False
        self._device = None
        self._pending = b""
        self._eof = False

    def setSource(self, url):
        self.stop()
        if self._reader:
            self._reader.close()
            self._reader = None
        if self._sink:
            self._sink.deleteLater()
            self._sink = None
        self._source = QUrl(url)
        self.underruns = 0
        self.bytes_streamed = 0
        self._set_status(QMediaPlayer.MediaStatus.NoMedia)
        if url.isEmpty():
            self.durationChanged.emit(0)
            return
        try:
            self._reader = wave.open(str(Path(url.toLocalFile())), "rb")
            if self._reader.getsampwidth() != 2 or self._reader.getcomptype() != "NONE":
                raise ValueError("Preview requires 16-bit PCM WAV audio.")
            self.durationChanged.emit(self.duration())
            self._set_status(QMediaPlayer.MediaStatus.LoadedMedia)
        except (OSError, ValueError, wave.Error) as error:
            if self._reader:
                self._reader.close()
                self._reader = None
            self._set_status(QMediaPlayer.MediaStatus.InvalidMedia)
            self.errorOccurred.emit(QMediaPlayer.Error.FormatError, str(error))

    def _create_sink(self):
        format = QAudioFormat()
        format.setSampleRate(self._reader.getframerate())
        format.setChannelCount(min(2, self._reader.getnchannels()))
        format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        if self._sink_factory:
            sink = self._sink_factory(format, self)
        else:
            device = QMediaDevices.defaultAudioOutput()
            if device.isNull():
                raise ValueError("No audio output is available. Connect headphones or speakers and try again.")
            if not device.isFormatSupported(format):
                # Some Windows devices expose only floating-point PCM.
                format.setSampleFormat(QAudioFormat.SampleFormat.Float)
                if not device.isFormatSupported(format):
                    raise ValueError("The audio output does not support this sample rate. Try another output device.")
            sink = QAudioSink(device, format, self)
        self._sample_format = format.sampleFormat()
        # The old 40 ms GUI-fed queue underruns when Windows occludes the UI.
        # A dedicated precise-timer thread and 200 ms queue tolerate background
        # scheduling delays without depending on repaint or window events.
        sink.setBufferSize(max(1024, format.bytesForDuration(200000)))
        sink.stateChanged.connect(self._sink_state)
        return sink

    def play(self):
        if not self._reader or self._state == QMediaPlayer.PlaybackState.PlayingState:
            return
        if self._state == QMediaPlayer.PlaybackState.PausedState and self._device:
            self._sink.resume()
        else:
            if self._status == QMediaPlayer.MediaStatus.EndOfMedia:
                self.setPosition(0)
            try:
                if not self._sink:
                    self._sink = self._create_sink()
                self._gain = 0.0 if self.output.isMuted() else self.output.volume()
                self._device = self._sink.start()
                if self._device is None:
                    raise ValueError("Audio output could not start.")
            except (RuntimeError, ValueError) as error:
                self.errorOccurred.emit(QMediaPlayer.Error.ResourceError, str(error))
                return
        self._set_status(QMediaPlayer.MediaStatus.BufferedMedia)
        self._set_state(QMediaPlayer.PlaybackState.PlayingState)
        self._timer.start()
        self._pump()

    def pause(self):
        if self._state == QMediaPlayer.PlaybackState.PlayingState:
            self._sink.suspend()
            self._timer.stop()
            self._set_state(QMediaPlayer.PlaybackState.PausedState)

    def stop(self):
        self._reset_sink()
        self._base_frame = self._last_position = 0
        if self._reader:
            self._reader.rewind()
            self._set_status(QMediaPlayer.MediaStatus.LoadedMedia)
        self._set_state(QMediaPlayer.PlaybackState.StoppedState)
        self.positionChanged.emit(0)

    def setPosition(self, milliseconds):
        if not self._reader:
            return
        playing = self._state == QMediaPlayer.PlaybackState.PlayingState
        paused = self._state == QMediaPlayer.PlaybackState.PausedState
        self._reset_sink()
        self._base_frame = min(self._reader.getnframes(), max(0, round(milliseconds * self._reader.getframerate() / 1000)))
        self._reader.setpos(self._base_frame)
        self._last_position = self.position()
        self._set_state(QMediaPlayer.PlaybackState.StoppedState)
        self._set_status(QMediaPlayer.MediaStatus.LoadedMedia)
        self.positionChanged.emit(self._last_position)
        if playing:
            self.play()
        elif paused:
            self._set_state(QMediaPlayer.PlaybackState.PausedState)

    def _pump(self):
        if not self._device or self._state != QMediaPlayer.PlaybackState.PlayingState:
            return
        free = self._sink.bytesFree()
        source_channels, rate = self._reader.getnchannels(), self._reader.getframerate()
        channels = min(2, source_channels)
        frame_bytes = channels * (4 if self._sample_format == QAudioFormat.SampleFormat.Float else 2)
        if not self._pending and not self._eof and free >= frame_bytes:
            frames = min(free // frame_bytes, 4096)
            pcm = preview_pcm(self._reader.readframes(frames), source_channels)
            target = 0.0 if self.output.isMuted() else self.output.volume()
            self._pending, self._gain = amplify(pcm, channels, self._gain, target, rate)
            if self._sample_format == QAudioFormat.SampleFormat.Float:
                self._pending = (np.frombuffer(self._pending, dtype="<i2").astype("<f4") / 32768).tobytes()
            self._eof = self._reader.tell() >= self._reader.getnframes()
        if self._pending and free:
            written = self._device.write(self._pending[:free])
            if written > 0:
                self._pending = self._pending[written:]
                self.bytes_streamed += written
        position = self.position()
        if abs(position - self._last_position) >= 30:
            self._last_position = position
            self.positionChanged.emit(position)
        if self._eof and not self._pending and self._sink.state() == QAudio.State.IdleState:
            self._ended()

    def _sink_state(self, state):
        if self._resetting:
            return
        if state == QAudio.State.IdleState and self._eof and not self._pending:
            self._ended()
        elif state == QAudio.State.IdleState and self._state == QMediaPlayer.PlaybackState.PlayingState:
            self.underruns += 1
        elif state == QAudio.State.StoppedState and self._sink and self._sink.error() != QAudio.Error.NoError:
            self._timer.stop()
            self._set_state(QMediaPlayer.PlaybackState.StoppedState)
            self.errorOccurred.emit(QMediaPlayer.Error.ResourceError, "Audio output was interrupted.")

    def _ended(self):
        self._reset_sink()
        self._base_frame = self._reader.getnframes()
        self._reader.setpos(self._base_frame)
        self._set_state(QMediaPlayer.PlaybackState.StoppedState)
        self._set_status(QMediaPlayer.MediaStatus.EndOfMedia)
        self.positionChanged.emit(self.duration())


class PreviewPlayer(QObject):
    """GUI-side transport; all sink, timer and file operations live off the UI."""
    positionChanged = Signal(int)
    playbackStateChanged = Signal(QMediaPlayer.PlaybackState)
    mediaStatusChanged = Signal(QMediaPlayer.MediaStatus)
    errorOccurred = Signal(QMediaPlayer.Error, str)
    _request = Signal(str, object)

    def __init__(self, parent=None, sink_factory=None):
        super().__init__(parent)
        self.output = PreviewOutput()
        self._source = QUrl()
        self._position = self._duration = 0
        self._state = QMediaPlayer.PlaybackState.StoppedState
        self._status = QMediaPlayer.MediaStatus.NoMedia
        self._closed = False
        self._thread = QThread(self)
        self._thread.setObjectName("Audio playback")
        self._engine = _PlaybackEngine(sink_factory=sink_factory)
        self._engine.output = self.output
        self._engine.moveToThread(self._thread)
        self._request.connect(self._engine.command, Qt.ConnectionType.QueuedConnection)
        self._engine.positionChanged.connect(self._on_position)
        self._engine.durationChanged.connect(self._on_duration)
        self._engine.playbackStateChanged.connect(self._on_state)
        self._engine.mediaStatusChanged.connect(self._on_status)
        self._engine.errorOccurred.connect(self.errorOccurred)
        self._thread.finished.connect(self._engine.deleteLater)
        self._thread.start(QThread.Priority.HighPriority)
        if QCoreApplication.instance():
            QCoreApplication.instance().aboutToQuit.connect(self.shutdown)

    @Slot(int)
    def _on_position(self, value):
        self._position = value
        self.positionChanged.emit(value)

    @Slot(int)
    def _on_duration(self, value):
        self._duration = value

    @Slot(QMediaPlayer.PlaybackState)
    def _on_state(self, value):
        self._state = value
        self.playbackStateChanged.emit(value)

    @Slot(QMediaPlayer.MediaStatus)
    def _on_status(self, value):
        self._status = value
        self.mediaStatusChanged.emit(value)

    def source(self): return self._source
    def position(self): return self._position
    def duration(self): return self._duration
    def playbackState(self): return self._state
    def mediaStatus(self): return self._status

    def setSource(self, url):
        if self._closed:
            return
        self._source = QUrl(url)
        self._position = self._duration = 0
        if url.isEmpty():
            # Release the reader before the GUI deletes its temporary WAVs.
            QMetaObject.invokeMethod(self._engine, "clear_source", Qt.ConnectionType.BlockingQueuedConnection)
            self._state = QMediaPlayer.PlaybackState.StoppedState
            self._status = QMediaPlayer.MediaStatus.NoMedia
        else:
            self._request.emit("source", QUrl(url))

    def play(self):
        if not self._closed:
            self._request.emit("play", None)

    def pause(self):
        if not self._closed:
            self._request.emit("pause", None)

    def stop(self):
        if not self._closed:
            self._request.emit("stop", None)

    def setPosition(self, value):
        if not self._closed:
            self._position = max(0, int(value))
            self._request.emit("position", self._position)

    @Slot()
    def shutdown(self):
        if self._closed:
            return
        self.setSource(QUrl())
        self._closed = True
        self._thread.quit()
        self._thread.wait(3000)
