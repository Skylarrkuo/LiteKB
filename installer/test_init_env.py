import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


INITIALIZER = Path(__file__).resolve().with_name("init_env.py")


def initialize(directory):
    subprocess.run([sys.executable, INITIALIZER], cwd=directory, capture_output=True, check=True)


class ComposeCredentialsTest(unittest.TestCase):
    def test_preserves_existing_values_and_format(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, ".env")
            original = b"# prior settings\r\nexport LITEKB_DB_PASSWORD='existing'\r\nLITEKB_MEDIA_NODES=1"
            path.write_bytes(original)
            initialize(directory)
            filled = path.read_bytes()
            self.assertTrue(filled.startswith(original + b"\r\n"))
            self.assertEqual(filled.count(b"LITEKB_DB_PASSWORD="), 1)
            self.assertEqual(filled.count(b"\r\n"), 6)
            initialize(directory)
            self.assertEqual(path.read_bytes(), filled)

    def test_parallel_initializers_generate_one_set_of_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            with ThreadPoolExecutor(max_workers=4) as executor:
                list(executor.map(initialize, [directory] * 4))
            path = Path(directory, ".env")
            pairs = [line.split("=", 1) for line in path.read_text().splitlines()]
            self.assertEqual(len(pairs), 4)
            values = dict(pairs)
            self.assertEqual(set(values), {
                "LITEKB_DB_PASSWORD", "LITEKB_REDIS_PASSWORD", "LITEKB_SECRET_KEY", "LITEKB_ADMIN_PASSWORD",
            })
            self.assertEqual(len(set(values.values())), 4)
            self.assertEqual(len(values["LITEKB_ADMIN_PASSWORD"]), 20)
            if os.name == "posix":
                self.assertEqual(path.stat().st_mode & 0o077, 0)
