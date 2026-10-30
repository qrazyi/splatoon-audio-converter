from pathlib import Path
import tempfile
import unittest
import wave

import numpy as np

from fixtures import replacement_wav
from splatoon_audio_converter.preview import Preview, waveform, with_volume


class PreviewVolumeTests(unittest.TestCase):
    def test_boost_is_real_and_only_changes_a_temporary_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "quiet.wav"
            replacement_wav(source)
            original = source.read_bytes()
            preview = Preview(source, *waveform(source), False)
            boosted = with_volume(preview, Path(folder) / "cache", 200)
            self.assertNotEqual(boosted.playback_path, source)
            self.assertEqual(boosted.gain, 200)
            self.assertAlmostEqual(waveform(boosted.playback_path)[2] - preview.peak_db, 6.0206, places=3)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(with_volume(boosted, Path(folder) / "cache", 75).playback_path, source)

    def test_boost_clips_safely_without_integer_overflow(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "loud.wav"
            with wave.open(str(source), "wb") as sound:
                sound.setparams((1, 2, 32000, 0, "NONE", "not compressed"))
                sound.writeframes(np.array([30000, -30000, 0], dtype="<i2").tobytes())
            preview = Preview(source, *waveform(source), False)
            boosted = with_volume(preview, Path(folder) / "cache", 200)
            with wave.open(str(boosted.playback_path), "rb") as sound:
                self.assertEqual(np.frombuffer(sound.readframes(3), dtype="<i2").tolist(), [32767, -32768, 0])
