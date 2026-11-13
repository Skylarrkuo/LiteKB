import shutil
import subprocess
from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless


@skipUnless(find_spec("pysilk") and find_spec("pydub") and shutil.which("ffmpeg"), "requires the media extra and ffmpeg")
class SilkAudioTests(TestCase):
    def test_speech_conversion_preserves_source_and_writes_decodable_mp3(self):
        import pysilk
        from common.utils.common import any_to_mp3

        with TemporaryDirectory() as temp:
            original = Path(temp) / "sample.silk"
            output = Path(temp) / "sample.mp3"
            encoded = pysilk.encode(b"\x10\x00" * 4800, sample_rate=24000)
            original.write_bytes(encoded)
            any_to_mp3(str(original), str(output))
            self.assertEqual(original.read_bytes(), encoded)
            audio = subprocess.check_output([
                "ffmpeg", "-v", "error", "-i", str(output), "-f", "s16le", "-ar", "16000", "-ac", "1", "pipe:1",
            ])
            self.assertGreater(len(audio), 0)
