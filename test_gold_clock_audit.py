# SPDX-License-Identifier: GPL-3.0-only
from datetime import datetime, timezone
import unittest

from orrery_gold_clock_audit import inherited_chain, scheduled_open


def stamp(value):
    return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp())


class GoldClockAuditTests(unittest.TestCase):
    def test_ny_break_changes_with_dst_and_weekend_stays_closed(self):
        self.assertTrue(scheduled_open(stamp('2025-03-07T21:30:00')))
        self.assertFalse(scheduled_open(stamp('2025-03-07T22:30:00')))
        self.assertFalse(scheduled_open(stamp('2025-03-10T21:30:00')))
        self.assertTrue(scheduled_open(stamp('2025-03-10T22:30:00')))
        self.assertFalse(scheduled_open(stamp('2025-03-08T12:00:00')))

    def test_inheritance_requires_every_skipped_minute_to_be_closed(self):
        start = stamp('2025-03-10T20:00:00')
        bars = [dict(close_time=start+3600), dict(close_time=start+10800)]
        prefix = [0]
        for t in range(start, start+10800, 60):
            prefix.append(prefix[-1]+scheduled_open(t))
        result = inherited_chain(bars, 3600, start, prefix)
        self.assertEqual(result['longest_chain'], 2)
        self.assertEqual(result['closed_gap_carries'], 1)
        self.assertEqual(inherited_chain(bars, 3600, start, list(range(181)))['longest_chain'], 1)
