import tempfile
import subprocess
import unittest
from pathlib import Path

import numpy as np

from splatoon_audio_converter import core
from splatoon_audio_converter.preview import waveform
from splatoon_audio_converter.updates import parse_release, version
from fixtures import bars, pcm_bwav, replacement_wav


class CoreTests(unittest.TestCase):
    def test_suffix_is_only_added_once(self):
        for name in ("sound", "sound.bars", "sound.bars.zs", "sound.bars.zs.bars.zs"):
            with self.subTest(name=name):
                self.assertEqual(core.bars_zs_name(name), "sound.bars.zs")
        for name in ("music", "music.bfstm", "music.bfstm.zs", "music.bfstm.zs.bfstm.zs"):
            self.assertEqual(core.bfstm_name(name, True), "music.bfstm.zs")

    def test_plain_bars_duration_and_names(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "sounds.bars"
            source.write_bytes(bars())
            document = core.BarsDocument(source)
            self.assertEqual(len(document.tracks), 3)
            self.assertAlmostEqual(document.tracks[0].duration, .32)
            self.assertEqual(document.tracks[0].name, "Preview_Chime")
            self.assertEqual(document.tracks[2].loop_end, document.tracks[2].sample_count)

    def test_compressed_and_plain_are_equivalent(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "sounds.bars.zs"
            raw = bars()
            source.write_bytes(core.Zstd().compress(raw))
            document = core.BarsDocument(source)
            self.assertEqual(document.bars, raw)
            self.assertTrue(document.was_compressed)

    def test_extraction_produces_only_wav(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "sounds.bars"
            source.write_bytes(bars())
            document = core.BarsDocument(source)
            destination = Path(folder) / "extracted"
            document.extract(document.tracks, destination)
            files = list(destination.iterdir())
            self.assertEqual(len(files), 3)
            self.assertTrue(all(path.suffix == ".wav" for path in files))
            self.assertEqual(source.read_bytes(), bars())

    def test_standalone_bwav(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "sound.bwav"
            source.write_bytes(pcm_bwav())
            document = core.BarsDocument(source)
            self.assertTrue(document.is_bwav)
            rate, channels = document.decode_track(document.tracks[0])
            self.assertEqual(rate, 32000)
            self.assertEqual(len(channels[0]), 10240)

    def test_waveform_levels_and_duration(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "replacement.wav"
            replacement_wav(path)
            peaks, duration, peak, average = waveform(path)
            self.assertEqual(len(peaks), 1200)
            self.assertAlmostEqual(duration, .5)
            self.assertTrue(-12 < peak < -10)
            self.assertLess(average, peak)
            self.assertTrue(np.all((peaks >= 0) & (peaks <= 1)))

    def test_empty_wav_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "empty.wav"
            replacement_wav(path, seconds=0)
            with self.assertRaisesRegex(ValueError, "no playable"):
                waveform(path)

    def test_save_without_replacements(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / "sounds.bars", Path(folder) / "new.bars.zs"
            source.write_bytes(bars())
            document = core.BarsDocument(source)
            result = document.build(target, lambda _: None)
            self.assertEqual(core.read_archive(target), bars())
            self.assertEqual(result["entries_replaced"], 0)
            with self.assertRaisesRegex(ValueError, "source archive"):
                document.build(source, lambda _: None)
            self.assertFalse(list(Path(folder).glob("*.json")))

    @unittest.skipUnless(__import__("sys").platform == "win32", "Bundled helper is Windows-only")
    def test_bars_wav_replacement_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / "sounds.bars", Path(folder) / "new.bars.zs"
            source.write_bytes(bars())
            wav = Path(folder) / "custom.wav"
            replacement_wav(wav)
            document = core.BarsDocument(source)
            document.replacements[document.tracks[0].name] = wav
            result = document.build(target, lambda _: None)
            reread = core.BarsDocument(target)
            self.assertEqual(result["entries_replaced"], 1)
            self.assertAlmostEqual(reread.tracks[0].duration, .5)
            self.assertEqual(reread.tracks[1].name, document.tracks[1].name)
            self.assertEqual(source.read_bytes(), bars())

    @unittest.skipUnless(__import__("sys").platform == "win32", "Bundled helper is Windows-only")
    def test_standalone_bwav_replacement_keeps_loop(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / "sound.bwav", Path(folder) / "new.bwav"
            source.write_bytes(pcm_bwav(loop=True))
            wav = Path(folder) / "new.wav"
            replacement_wav(wav)
            document = core.BarsDocument(source)
            document.replacements[document.tracks[0].name] = wav
            document.build(target, lambda _: None)
            reread = core.BarsDocument(target)
            self.assertAlmostEqual(reread.tracks[0].duration, .5)
            self.assertEqual(reread.tracks[0].loop_end, reread.tracks[0].sample_count)

    @unittest.skipUnless(__import__("sys").platform == "win32", "Bundled helper is Windows-only")
    def test_bfstm_open_preview_replace_and_extract(self):
        fixture_tool = Path(__file__).resolve().parents[1] / "test-output/make_test_stream.exe"
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "music.bfstm"
            wav = Path(folder) / "original.wav"
            replacement_wav(wav, seconds=.4)
            subprocess.run([str(fixture_tool), str(wav), str(source)], check=True, capture_output=True)
            document = core.BarsDocument(source)
            self.assertTrue(document.is_stream)
            self.assertAlmostEqual(document.tracks[0].duration, .4)
            document.extract(document.tracks, Path(folder) / "extract")
            self.assertEqual(len(list((Path(folder) / "extract").glob("*.wav"))), 1)
            replacement_wav(wav, seconds=.7)
            document.replacements[document.tracks[0].name] = wav
            target = Path(folder) / "modified.bfstm"
            document.build(target, lambda _: None)
            reread = core.BarsDocument(target)
            self.assertAlmostEqual(reread.tracks[0].duration, .7)
            self.assertEqual(reread.tracks[0].loop_end, reread.tracks[0].sample_count)

    def test_updates_are_validated_and_read_only(self):
        with self.assertRaises(ValueError):
            version("latest")
        self.assertIsNone(parse_release({"tag_name": "v1.0.0"}))
        self.assertIsNone(parse_release({"tag_name": "v9.0.0", "prerelease": True}))
        with self.assertRaises(ValueError):
            parse_release({"tag_name": "v9.0.0", "html_url": "https://example.com/download"})
        release = parse_release({"tag_name": "v9.0.0", "html_url": "https://github.com/qrazyi/splatoon-audio-converter/releases/tag/v9.0.0"})
        self.assertEqual(release.version, "v9.0.0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
