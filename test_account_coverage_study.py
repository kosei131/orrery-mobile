import unittest

from lsr03_account_replay import replay_account
from orrery_account_coverage_study import replay_continuous_window
from test_lsr03_account_replay import T, plan, pnl, q


INPUTS = dict(symbol='XAUUSD', volume_min=.01, volume_max=100, volume_step=.01,
              pnl_quote=pnl, round_trip_cost_per_lot_usd=.1,
              cost_source='SYNTHETIC_LINEAR_USD_ONLY', slippage=0)


class CoverageTests(unittest.TestCase):
    def run_window(self, quotes, **overrides):
        options = dict(start_msc=T, end_msc=T+3000, max_gap_msc=1000, **INPUTS)
        options.update(overrides)
        return replay_continuous_window(iter(quotes), [plan()], **options)

    def test_dense_window_matches_existing_account_engine(self):
        quotes = [q(1), q(1000, 102, 102.1), q(2000)]
        result = self.run_window(quotes)
        self.assertEqual(result['account'], replay_account(quotes, [plan()], **INPUTS))
        self.assertLessEqual(result['account']['decisions'][0]['planned_risk_usd'], 7.5)

    def test_open_position_does_not_fill_across_gap(self):
        result = self.run_window([q(1), q(2000, 102, 102.1)])
        self.assertIsNone(result['account'])
        self.assertEqual(result['gap'], dict(start_msc=T+1, end_msc=T+2000, edge='INTERIOR'))

    def test_incomplete_tail_suppresses_previously_closed_trade_metrics(self):
        result = self.run_window([q(1), q(1000, 102, 102.1)])
        self.assertIsNone(result['account'])
        self.assertEqual(result['gap']['edge'], 'END')

    def test_empty_and_late_start_are_distinct(self):
        self.assertEqual(self.run_window([])['gap']['edge'], 'EMPTY')
        self.assertEqual(self.run_window([q(1001)])['gap']['edge'], 'START')

    def test_future_quote_and_wrong_boundary_rejected(self):
        with self.assertRaises(ValueError):
            self.run_window([q(1), q(3000)])
        with self.assertRaises(ValueError):
            self.run_window([q(1)], daily_boundary_utc_hour=0)
