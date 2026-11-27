# SPDX-License-Identifier: GPL-3.0-only
import unittest

from orrery_gold_hourly_trend import signals


class GoldHourlyTrendTests(unittest.TestCase):
    def setUp(self):
        self.at = 44*3600
        self.h4 = [dict(close_time=(i+1)*14400, close=100+i) for i in range(11)]
        self.h1 = [dict(close_time=self.at-(20-i)*3600, close=p, high=p+1, low=p-1)
                   for i,p in enumerate([100]*19+[90,101])]

    def test_h4_is_available_only_after_close(self):
        [at_close] = signals(self.h1, self.h4, self.at+1)
        self.assertEqual(at_close['h4_direction'], 'BUY')
        earlier = [dict(row, close_time=row['close_time']-3600) for row in self.h1]
        [before_close] = signals(earlier, self.h4, self.at+1)
        self.assertIsNone(before_close['h4_direction'])

    def test_gap_rejects_hourly_setup(self):
        self.h1[3]['close_time'] -= 60
        self.assertEqual(list(signals(self.h1, self.h4, self.at+1)), [])
