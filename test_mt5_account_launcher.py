"""Launcher orchestration tests; actual terminal behavior belongs to pilot tests."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import START_MT5_ACCOUNT_COMPARISON as launcher
from test_lsr03_mt5_account_pilot import config


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'lsr03_mt5_account_pilot.py').touch()
        self.terminal = self.root / 'terminal with spaces.exe'
        self.terminal.touch()
        self.settings = self.root / 'settings.json'
        self.settings.write_text(json.dumps(config()))
        self.pin = 'a' * 64
        self.capture = self.root / 'capture with spaces'

    def run_launcher(self, code=0, output='new account'):
        answers = [str(self.capture), self.pin, str(self.settings), str(self.terminal), output]
        with patch.object(launcher.sys, 'platform', 'win32'), \
             patch.object(launcher, 'ask', side_effect=answers), \
             patch.object(launcher, 'verify_pilot_bundle', return_value=(
                 {'broker_valuation_spec': {'currency_profit': 'USD'}},
                 {'settings.json': {'symbol': 'XAUUSD'}})) as verify, \
             patch.object(launcher.subprocess, 'call', return_value=code) as call, \
             patch('builtins.print'):
            result = launcher.main(self.root)
            return result, call.call_args, verify.call_args

    def test_preserves_independent_pin_paths_and_runner_status(self):
        for code in (0, 1, 2):
            with self.subTest(code=code):
                result, called, verified = self.run_launcher(code)
                self.assertEqual(result, code)
                self.assertEqual(verified.args, (self.capture, self.pin))
                args = called.args[0]
                self.assertIsInstance(args, list)
                self.assertEqual(args[args.index('--pilot') + 1], str(self.capture))
                self.assertEqual(args[args.index('--pilot-run-sha256') + 1], self.pin)
                self.assertEqual(args[args.index('--terminal-path') + 1], str(self.terminal))
                self.assertEqual(called.kwargs, {'cwd': self.root})
                self.assertFalse((self.root / 'new account').exists())

    def test_bad_costs_do_not_start_child(self):
        self.settings.write_text(json.dumps(dict(config(), round_trip_cost_per_lot_usd=None)))
        with patch.object(launcher.sys, 'platform', 'win32'), \
             patch.object(launcher, 'ask', side_effect=[str(self.capture), self.pin, str(self.settings)]), \
             patch.object(launcher, 'verify_pilot_bundle', return_value=(
                 {'broker_valuation_spec': {'currency_profit': 'USD'}},
                 {'settings.json': {'symbol': 'XAUUSD'}})), \
             patch.object(launcher.subprocess, 'call') as call, patch('builtins.print'):
            with self.assertRaises(ValueError): launcher.main(self.root)
            call.assert_not_called()

    def test_existing_or_escaping_output_rejected(self):
        for name in ('settings.json', '..', '../outside'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.run_launcher(output=name)

    def test_hash_failure_never_starts_runner(self):
        with patch.object(launcher.sys, 'platform', 'win32'), \
             patch.object(launcher, 'ask', side_effect=[str(self.capture), self.pin]), \
             patch.object(launcher, 'verify_pilot_bundle', side_effect=ValueError('pin mismatch')), \
             patch.object(launcher.subprocess, 'call') as call, patch('builtins.print'):
            with self.assertRaises(ValueError): launcher.main(self.root)
            call.assert_not_called()

    def test_non_windows_stops_before_any_prompt(self):
        with patch.object(launcher.sys, 'platform', 'linux'), patch.object(launcher, 'ask') as ask:
            with self.assertRaises(RuntimeError): launcher.main(self.root)
            ask.assert_not_called()


if __name__ == '__main__': unittest.main()
