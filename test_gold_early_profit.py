# SPDX-License-Identifier: GPL-3.0-only
import unittest

from orrery_gold_early_profit import capped_result


class GoldEarlyProfitTests(unittest.TestCase):
    def quotes(self):
        bid = {0: dict(open=100, high=100.8, low=99.5, close=100.3)}
        ask = {0: dict(open=100.1, high=100.9, low=99.6, close=100.4)}
        return bid, ask

    def test_profit_cap_uses_executable_entry_and_original_stop(self):
        bid, ask = self.quotes()
        row = dict(at_utc=0, side='BUY', stop=99, target=101.75)
        result = capped_result(row, bid, ask)
        self.assertEqual(result['exit_reason'], 'TP_TOUCH')
        self.assertEqual(result['stop'], 99)
        self.assertAlmostEqual(result['entry'], 100.1)
        self.assertAlmostEqual(result['target'], 100.65)
        self.assertAlmostEqual(result['r'], 0.5)

    def test_nearer_original_target_is_preserved(self):
        bid, ask = self.quotes()
        result = capped_result(dict(at_utc=0, side='BUY', stop=99, target=100.3), bid, ask)
        self.assertAlmostEqual(result['target'], 100.3)
