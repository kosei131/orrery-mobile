# SPDX-License-Identifier: GPL-3.0-only
import unittest

from orrery_gold_pullback_study import replay
from orrery_gold_reversal_comparison import LOOKBACK, M15, reclaims, reverse_signals


class GoldReversalTests(unittest.TestCase):
    def test_reverse_uses_other_quote_and_swapped_absolute_levels(self):
        bid = {0: dict(open=100, high=102, low=96, close=98)}
        ask = {0: dict(open=101, high=103, low=97, close=99)}
        original = dict(at_utc=0, setup_at_utc=0, side='BUY', stop=97)
        [signal] = reverse_signals([original], bid, ask)
        self.assertEqual((signal['side'], signal['stop'], signal['target_price']), ('SELL', 103, 97))
        [row], _ = replay([signal], bid, ask, 0.5)
        self.assertEqual(row['status'], 'AMBIGUOUS_SAME_MINUTE')

    def test_reclaim_requires_single_sweep_and_contiguous_lookback(self):
        prior = [dict(close_time=i*M15, high=102, low=98, close=100)
                 for i in range(1, LOOKBACK+1)]
        current = dict(close_time=(LOOKBACK+1)*M15, high=101, low=97, close=100)
        [signal] = reclaims(prior+[current], {})
        self.assertEqual((signal['side'], signal['stop']), ('BUY', 97))
        self.assertEqual(list(reclaims(prior+[dict(current, high=103)], {})), [])
        broken = [dict(prior[0], close_time=0), *prior[1:]]
        self.assertEqual(list(reclaims(broken+[current], {})), [])
