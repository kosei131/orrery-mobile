# SPDX-License-Identifier: GPL-3.0-only
from datetime import time, timezone
import unittest
from unittest.mock import patch

from orrery_gold_session_breakout import session_signals


class GoldSessionBreakoutTests(unittest.TestCase):
    def test_first_breakout_is_classified_at_close(self):
        bars = [dict(close_time=t, high=105, low=95, close=100) for t in (900, 1800)]
        first = dict(close_time=2700, high=106, low=96, close=106)
        later = dict(close_time=3600, high=108, low=96, close=102)
        with patch('orrery_gold_session_breakout.SESSIONS', {'TEST': ('UTC', time(0))}), \
             patch('orrery_gold_session_breakout.ZoneInfo', return_value=timezone.utc):
            [signal] = session_signals(bars+[first, later], {}, {}, 0, 7200)
            self.assertEqual((signal['at_utc'], signal['side'], signal['pattern']),
                             (2700, 'BUY', 'CONTINUATION'))
            self.assertEqual(list(session_signals(bars+[later], {}, {}, 0, 7200)), [])
            double_break = dict(first, low=94)
            self.assertEqual(list(session_signals(bars+[double_break, later], {}, {}, 0, 7200)), [])
