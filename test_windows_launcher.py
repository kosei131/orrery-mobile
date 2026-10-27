"""Exercise the actual Windows CMD with public pinned sources; no MT5 or credentials."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.name == 'nt', 'Windows CMD integration only')
class WindowsLauncherTests(unittest.TestCase):
    def run_launcher(self, corrupt_hash=False):
        source = Path('VERIFY_MT5_WINDOWS.cmd').read_text(encoding='utf-8')
        if corrupt_hash:
            source, count = re.subn(r'(call :download mt5_local_dashboard.py )[0-9a-f]{64}',
                                   r'\g<1>' + '0' * 64, source)
            self.assertEqual(count, 1)
        with tempfile.TemporaryDirectory(prefix='orrery launcher ') as folder:
            root = Path(folder)
            launcher = root / 'verify.cmd'
            launcher.write_text(source, encoding='utf-8')
            sentinel = root / 'mt5_local_dashboard.py'
            sentinel.write_text('DO NOT OVERWRITE', encoding='utf-8')
            env = dict(os.environ, TEMP=folder, TMP=folder)
            result = subprocess.run(['cmd.exe', '/d', '/c', 'verify.cmd', '--verify-only'],
                                    cwd=folder, env=env, capture_output=True, text=True,
                                    timeout=240)
            self.assertEqual(sentinel.read_text(encoding='utf-8'), 'DO NOT OVERWRITE')
            output = result.stdout + result.stderr
            # Do not echo captured process output: regressions could contain a token.
            self.assertNotRegex(output, r'http://127\.0\.0\.1:8765/#')
            return result.returncode, output

    def test_pinned_downloads_and_offline_tests(self):
        code, output = self.run_launcher()
        self.assertEqual(code, 0, 'Launcher failed; captured output intentionally withheld')
        self.assertIn('[PASS] Offline tests passed.', output)
        self.assertIn('Ran 13 tests', output)

    def test_bad_hash_stops_before_python_tests(self):
        code, output = self.run_launcher(corrupt_hash=True)
        self.assertNotEqual(code, 0)
        self.assertIn('[FAIL]', output)
        self.assertNotIn('[PASS]', output)
        self.assertNotIn('Ran 13 tests', output)


if __name__ == '__main__':
    unittest.main()
