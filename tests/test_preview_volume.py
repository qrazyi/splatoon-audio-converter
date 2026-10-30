import unittest
import numpy as np

from splatoon_audio_converter.playback import PreviewOutput, amplify


class PreviewVolumeTests(unittest.TestCase):
    def test_real_300_percent_gain_without_mutating_source(self):
        source = np.array([1000, -2000, 0, 5000], dtype="<i2").tobytes()
        before = bytes(source)
        result, gain = amplify(source, 1, 3.0, 3.0, 32000)
        self.assertEqual(np.frombuffer(result, dtype="<i2").tolist(), [3000, -6000, 0, 15000])
        self.assertEqual(gain, 3)
        self.assertEqual(source, before)

    def test_boost_clips_safely_without_overflow(self):
        source = np.array([30000, -30000, 0], dtype="<i2").tobytes()
        result, _ = amplify(source, 1, 3, 3, 32000)
        self.assertEqual(np.frombuffer(result, dtype="<i2").tolist(), [32767, -32768, 0])

    def test_gain_changes_have_a_short_ramp_and_stereo_balance(self):
        source = np.full((512, 2), 1000, dtype="<i2").tobytes()
        result, gain = amplify(source, 2, 1, 3, 32000)
        result = np.frombuffer(result, dtype="<i2").reshape(-1, 2)
        self.assertTrue(1000 < result[0, 0] < 1100)
        self.assertEqual(result[-1, 0], 3000)
        self.assertTrue(np.array_equal(result[:, 0], result[:, 1]))
        self.assertEqual(gain, 3)

    def test_unity_gain_preserves_exact_bytes_and_output_has_300_percent_range(self):
        source = np.array([32767, -32768], dtype="<i2").tobytes()
        self.assertEqual(amplify(source, 1, 1, 1, 32000)[0], source)
        output = PreviewOutput()
        output.setVolume(3)
        self.assertEqual(output.volume(), 3)
        output.setVolume(10)
        self.assertEqual(output.volume(), 3)
