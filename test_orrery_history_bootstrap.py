import ast
import os
from hashlib import sha256
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import orrery_history_bootstrap as bootstrap


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)/'path with spaces'
        self.source = Path(__file__).resolve().parent

    def download(self, name):
        return (self.source/name).read_bytes()

    def test_exact_source_pins_and_fresh_folders(self):
        first = bootstrap.prepare(self.parent, download=self.download)
        second = bootstrap.prepare(self.parent, download=self.download)
        self.assertNotEqual(first, second)
        for name, pin in bootstrap.PINS.items():
            self.assertEqual(sha256((first/name).read_bytes()).hexdigest(), pin)
        self.assertEqual((first/'SOURCE_REVISION.txt').read_text().strip(), bootstrap.REVISION)

    def test_transitive_repository_imports_are_pinned(self):
        pending = ['orrery_mt5_history_check.py']; seen = set()
        while pending:
            name = pending.pop()
            if name in seen: continue
            self.assertIn(name, bootstrap.PINS)
            seen.add(name)
            for node in ast.walk(ast.parse(self.download(name))):
                names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                         else [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
                for module in names:
                    candidate = module.split('.')[0]+'.py'
                    if (self.source/candidate).exists(): pending.append(candidate)
        self.assertEqual(seen, set(bootstrap.PINS))

    def test_bad_hash_leaves_no_verified_marker(self):
        with self.assertRaises(ValueError):
            bootstrap.prepare(self.parent, download=lambda name: b'bad bytes')
        self.assertEqual(list(self.parent.rglob('SOURCE_REVISION.txt')), [])

    def test_network_failure_leaves_no_verified_marker(self):
        with self.assertRaises(OSError):
            bootstrap.prepare(self.parent, download=unittest.mock.Mock(side_effect=OSError))
        self.assertEqual(list(self.parent.rglob('SOURCE_REVISION.txt')), [])

    def test_oversized_response_rejected(self):
        with self.assertRaises(ValueError):
            bootstrap.prepare(self.parent, download=lambda name: b'x'*(bootstrap.MAX_BYTES+1))

    def cli(self, options=(), child_code=0, timeout=False):
        root = self.parent/'code folder'
        with patch.object(bootstrap.sys, 'argv', ['bootstrap', *options]), \
             patch.object(bootstrap.sys, 'platform', 'win32'), \
             patch.object(bootstrap.sys, 'version_info', (3,12)), \
             patch.dict(bootstrap.os.environ, LOCALAPPDATA=str(self.parent)), \
             patch.object(bootstrap, 'prepare', return_value=root), \
             patch.object(bootstrap.subprocess, 'run',
                 side_effect=subprocess.TimeoutExpired('synthetic',120) if timeout else None,
                 return_value=subprocess.CompletedProcess([], child_code)) as launch, \
             patch('builtins.print'):
            result = bootstrap.main()
            return result, launch

    def test_verify_only_never_starts_terminal_runner(self):
        code, launch = self.cli(['--verify-only'])
        self.assertEqual(code, 0); launch.assert_not_called()

    def test_fixed_runner_and_exit_codes(self):
        for status in (0,1,2):
            code, launch = self.cli(child_code=status)
            self.assertEqual(code, status)
            self.assertEqual(launch.call_args.args[0][1],
                             str(self.parent/'code folder'/'orrery_mt5_history_check.py'))
            self.assertEqual(launch.call_args.kwargs['timeout'], 120)
            self.assertNotIn('shell', launch.call_args.kwargs)

    def test_child_timeout_is_failure(self):
        code, _ = self.cli(timeout=True)
        self.assertEqual(code, 1)

    @unittest.skipUnless(os.name == 'nt', 'Windows Python launcher integration only')
    def test_windows_launcher_real_public_download_without_mt5(self):
        result = subprocess.run(['py', '-3.12', str(self.source/'orrery_history_bootstrap.py'),
                                 '--verify-only'], cwd=self.temp.name,
                                env=dict(os.environ, LOCALAPPDATA=self.temp.name),
                                capture_output=True, timeout=240)
        self.assertEqual(result.returncode, 0, 'Pinned download verification failed')
        self.assertIn(b'VERIFY_ONLY: No MT5 connection requested.', result.stdout)
        self.assertFalse((Path(self.temp.name)/'ORRERYFX'/'history-checks').exists())


if __name__ == '__main__': unittest.main()
