"""No broker connection: exercise safety gates with a fake MT5 module."""
import argparse
import ast
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import mt5_local_dashboard as dashboard


class SnapshotSafetyTests(unittest.TestCase):
    def setUp(self):
        self.mt5 = Mock()
        self.mt5.ACCOUNT_TRADE_MODE_DEMO = 0
        self.mt5.POSITION_TYPE_BUY = 0
        self.mt5.initialize.return_value = True
        self.mt5.account_info.return_value = SimpleNamespace(
            trade_mode=0, server='TEST-DEMO', login=12345678, currency='USD',
            balance=10000, equity=10001, margin_free=9000)
        self.mt5.positions_get.return_value = [SimpleNamespace(
            symbol='TEST', type=0, volume=.01, profit=1)]
        self.mt5.history_deals_get.return_value = []
        self.patches = [patch.object(dashboard, 'mt5', self.mt5),
                        patch.object(dashboard, 'ARGS', argparse.Namespace(test_data=False))]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_real_and_contest_accounts_rejected_before_data_read(self):
        for mode in (1, 2, None):
            with self.subTest(mode=mode):
                self.mt5.account_info.return_value.trade_mode = mode
                with self.assertRaisesRegex(RuntimeError, 'DEMO accounts only'):
                    dashboard.snapshot()
                self.mt5.positions_get.assert_not_called()
                self.mt5.history_deals_get.assert_not_called()
        self.assertEqual(self.mt5.shutdown.call_count, 3)

    def test_demo_snapshot_masks_account(self):
        result = dashboard.snapshot()
        self.assertEqual(result['status'], 'READ_ONLY_DEMO')
        self.assertEqual(result['account_last4'], '5678')
        self.assertNotIn('12345678', str(result))
        self.mt5.shutdown.assert_called_once()

    def test_missing_account_and_read_failures_always_shutdown(self):
        for method in ('account_info', 'positions_get', 'history_deals_get'):
            with self.subTest(method=method):
                mock = getattr(self.mt5, method)
                original = mock.return_value
                mock.return_value = None
                with self.assertRaises(RuntimeError):
                    dashboard.snapshot()
                mock.return_value = original
        self.assertEqual(self.mt5.shutdown.call_count, 3)

    def test_simulation_never_initializes_mt5(self):
        dashboard.ARGS.test_data = True
        self.assertEqual(dashboard.snapshot()['status'], 'SIMULATED_TEST_DATA')
        self.mt5.initialize.assert_not_called()

    def test_http_errors_do_not_expose_exception_details(self):
        handler = object.__new__(dashboard.Handler)
        handler.path = '/api/snapshot'
        handler.headers = {'Host': '127.0.0.1:8765', 'X-Orrery-Token': dashboard.TOKEN}
        handler.respond = Mock()
        with patch.object(dashboard, 'snapshot', side_effect=RuntimeError('PRIVATE_ACCOUNT_SECRET')):
            handler.do_GET()
        status, body, _ = handler.respond.call_args.args
        self.assertEqual(status, 503)
        self.assertNotIn('PRIVATE_ACCOUNT_SECRET', body)
        self.assertIn('DEMO', json.loads(body)['error'])

    def test_only_readonly_mt5_calls_exist_in_both_scripts(self):
        allowed = {'initialize', 'account_info', 'positions_get',
                   'history_deals_get', 'last_error', 'shutdown', 'symbol_info_tick', 'copy_rates_from_pos'}
        for filename in ('mt5_local_dashboard.py', 'mt5_readonly.py'):
            tree = ast.parse(Path(filename).read_text(encoding='utf-8'))
            calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Attribute)
                     and isinstance(n.func.value, ast.Name) and n.func.value.id == 'mt5'}
            self.assertTrue(calls <= allowed, (filename, calls - allowed))


if __name__ == '__main__':
    unittest.main()
