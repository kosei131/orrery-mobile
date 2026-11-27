# SPDX-License-Identifier: GPL-3.0-only
import unittest

from orrery_gold_pullback_study import evaluate_pullback, hourly_directions, signals, suspect_flat_minutes


class GoldPullbackStudyTests(unittest.TestCase):
    def test_hourly_direction_requires_contiguous_completed_history(self):
        hours = [{'close_time': i * 3600, 'close': 100 + i} for i in range(13)]
        self.assertEqual(list(hourly_directions(hours)), [(12 * 3600, 'BUY')])
        self.assertEqual(list(hourly_directions(hours[:5] + hours[6:])), [])
        m5 = [{'close_time': 12 * 3600 - 300, 'close': 100, 'high': 101, 'low': 99},
              {'close_time': 12 * 3600, 'close': 102, 'high': 103, 'low': 98}]
        m15 = [{'close_time': 12 * 3600 - 300, 'open': 102, 'close': 100, 'low': 98}]
        self.assertEqual(list(signals(m5, m15, hours, {})), [])

    def test_suspect_flat_run_does_not_bridge_gap_or_price_change(self):
        flat = dict(open=100, high=100, low=100, close=100)
        shifted = dict(open=101, high=101, low=101, close=101)
        short = {i * 60: flat for i in range(59)}
        long = {i * 60: flat for i in range(60, 120)}
        self.assertEqual(list(suspect_flat_minutes(short | long | {7200: shifted})), list(long))

    def test_small_target_keeps_same_bid_ask_entry_and_stop(self):
        bid = {0: dict(open=100, high=102.5, low=99, close=101)}
        ask = {0: dict(open=101, high=103, low=100, close=102)}
        plan = dict(first_poi_touch_close=0, side='BUY')
        args = dict(structural_stop=98.5, structural_known_at=0, horizon=1)
        small = evaluate_pullback(plan, bid, ask, target_r=0.5, **args)
        wide = evaluate_pullback(plan, bid, ask, **args)
        self.assertEqual((small['entry'], small['stop'], small['r']), (101, 98.5, 0.5))
        self.assertEqual(small['exit_reason'], 'TP_TOUCH')
        self.assertEqual(wide['exit_reason'], 'TIMEOUT_CLOSE')
