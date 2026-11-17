# SPDX-License-Identifier: GPL-3.0-only
import unittest

from orrery_gold_band_reentry import signals


class GoldBandReentryTests(unittest.TestCase):
    def bars(self):
        return [dict(close_time=(i+1)*900, close=p, high=p+1, low=p-1)
                for i,p in enumerate([100]*19+[90,97])]

    def test_signal_uses_only_completed_prior_bars_and_known_center(self):
        bars = self.bars()
        [signal] = signals(bars, 999999)
        self.assertEqual((signal['side'], signal['target']), ('BUY', 99.5))
        future = dict(close_time=19800, close=1000, high=1001, low=999)
        self.assertEqual(list(signals(bars+[future], 999999))[0], signal)

    def test_signal_rejects_gap_in_indicator_history(self):
        bars = self.bars()
        bars[5]['close_time'] -= 60
        self.assertEqual(list(signals(bars, 999999)), [])
