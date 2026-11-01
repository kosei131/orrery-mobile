import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from orrery_mt5_history_check import check_history
from lsr04_tick_archive import verify_tick_archive


class Feed:
    ACCOUNT_TRADE_MODE_DEMO = 0
    COPY_TICKS_ALL = 1

    def __init__(self):
        self.login = 1
        self.mode = 0
        self.empty = False
        self.switch = False
        self.spread = .1

    def account_info(self):
        return SimpleNamespace(login=self.login, server='private', currency='USD',
                               trade_mode=self.mode)

    def symbol_info(self, symbol):
        return SimpleNamespace(name=symbol, point=.01, trade_contract_size=100., digits=2)

    def copy_ticks_range(self, symbol, start, end, flags):
        if self.switch:
            self.login = 2
        if self.empty:
            return []
        return [dict(time_msc=int(start.timestamp()*1000)+i*1000,
                     bid=2000., ask=2000.+self.spread) for i in range(600)]


class HistoryCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)/'new'
        self.start = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)
        self.args = dict(output=self.output, symbol='XAUUSD', start=self.start,
                         end=self.start+timedelta(minutes=10),
                         now=self.start+timedelta(minutes=12))

    def test_roundtrip_no_costs_or_secrets(self):
        result = check_history(Feed(), **self.args)
        self.assertEqual(result['status'], 'HISTORY_SAVED_REVIEW_REQUIRED')
        self.assertEqual(result['rows'], 600)
        verified = verify_tick_archive(self.output/'archive',
            expected_manifest_sha256=result['manifest_sha256'])
        self.assertEqual(verified['row_count'], 600)
        self.assertFalse(result['backtest_ready'])
        self.assertFalse(result['profitability_evaluated'])
        self.assertFalse(result['execution_allowed'])
        for path in self.output.rglob('*.json'):
            self.assertNotIn('private', path.read_text())
            self.assertNotIn('login', path.read_text())

    def test_real_account_stops(self):
        feed = Feed(); feed.mode = 2
        with self.assertRaises(ValueError): check_history(feed, **self.args)
        self.assertFalse(self.output.exists())

    def test_account_switch_stops(self):
        feed = Feed(); feed.switch = True
        with self.assertRaises(ValueError): check_history(feed, **self.args)
        self.assertFalse(self.output.exists())

    def test_empty_stops(self):
        feed = Feed(); feed.empty = True
        with self.assertRaises(ValueError): check_history(feed, **self.args)

    def test_cap_stops(self):
        with patch('orrery_mt5_history_check.MAX_TICKS', 600):
            with self.assertRaises(ValueError): check_history(Feed(), **self.args)

    def test_quality_failure_preserves_evidence(self):
        feed = Feed(); feed.spread = 2.
        result = check_history(feed, **self.args)
        self.assertEqual(result['status'], 'BLOCKED_HISTORY_QUALITY')
        self.assertTrue((self.output/'history_check.json').exists())

    def test_interrupted_save_has_no_completion_marker(self):
        with patch('orrery_mt5_history_check.verify_tick_archive', side_effect=ValueError):
            with self.assertRaises(ValueError): check_history(Feed(), **self.args)
        self.assertFalse((self.output/'history_check.json').exists())

    def test_existing_output_not_overwritten(self):
        self.output.mkdir(); sentinel = self.output/'sentinel'
        sentinel.write_text('keep')
        with self.assertRaises(FileExistsError): check_history(Feed(), **self.args)
        self.assertEqual(sentinel.read_text(), 'keep')

    def test_bad_bounds(self):
        for changes in (dict(end=self.start+timedelta(minutes=11)),
                        dict(now=self.start), dict(start=self.start.replace(tzinfo=None)),
                        dict(symbol='XAUUSD.fake')):
            with self.assertRaises(ValueError):
                check_history(Feed(), **dict(self.args, **changes))


if __name__ == '__main__':
    unittest.main()
