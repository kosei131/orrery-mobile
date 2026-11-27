import unittest

from orrery_gold_entry_family_comparison import h4_context


class EntryContextTests(unittest.TestCase):
    def test_closed_contiguous_h4_only(self):
        bars = [
            dict(close_time=14400, high=100, low=90),
            dict(close_time=28800, high=105, low=92),
            dict(close_time=43200, high=115, low=94),
            dict(close_time=57600, high=1000, low=1),
        ]
        clocks = [bar['close_time'] for bar in bars]
        at_close = h4_context(bars, clocks, 43200)
        self.assertEqual(at_close['direction'], 'UP')
        self.assertEqual(at_close['range_state'], 'EXPANDING')
        self.assertEqual(h4_context(bars, clocks, 57599), at_close)
        self.assertEqual(h4_context(bars[:3], clocks[:3], 57600)['direction'], 'UNKNOWN')
        self.assertEqual(h4_context(bars[1:], clocks[1:], 43200)['direction'], 'UNKNOWN')
