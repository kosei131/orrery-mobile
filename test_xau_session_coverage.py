import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from orrery_xau_session_coverage import crosscheck, weekly_open

class SessionCoverageTests(unittest.TestCase):
    def test_published_weekly_boundaries(self):
        for stamp, expected in [('2026-10-26T20:59',True), ('2026-10-26T21:00',False),
                                ('2026-10-26T21:59',False), ('2026-10-26T22:00',True),
                                ('2026-10-23T20:44',True), ('2026-10-23T20:45',False),
                                ('2026-10-24T12:00',False), ('2026-10-25T21:59',False),
                                ('2026-10-25T22:00',True)]:
            with self.subTest(stamp=stamp):
                self.assertEqual(weekly_open(dt.datetime.fromisoformat(stamp)), expected)

    def run_case(self, stamps):
        with tempfile.TemporaryDirectory() as folder:
            src=Path(folder)/'source.csv'
            with src.open('w', newline='', encoding='utf-8') as f:
                w=csv.writer(f)
                w.writerow(['timestamp_utc','bid_open','bid_high','bid_low','bid_close'])
                for t in stamps:
                    w.writerow([t,100,101,99,100])
            return crosscheck(src,Path(folder)/'out')

    def test_known_closure_partial_bar_and_unknown_missing_are_separate(self):
        start=dt.datetime(2026,10,26,20,tzinfo=dt.timezone.utc)
        stamps=[(start+dt.timedelta(minutes=m)).isoformat() for m in range(240)
                if m<60 or m>=120]
        r=self.run_case(stamps)
        self.assertEqual(r['missing_open_minutes'],0)
        self.assertEqual(r['h4_aggregation']['complete_session_partial_bars'],1)
        self.assertFalse(r['h4_strategy_ready'])
        stamps.pop(5)
        r=self.run_case(stamps)
        self.assertEqual(r['missing_open_minutes'],1)
        self.assertEqual(r['h4_aggregation']['complete_bars'],0)

    def test_closure_conflict_blocks_export(self):
        r=self.run_case(['2026-10-26T21:00:00+00:00'])
        self.assertEqual(r['quotes_during_published_closure'],1)
        self.assertIsNone(r['h4_aggregation'])
        self.assertIsNone(r['profit_usd'])

    def test_edge_truncation_not_reported_as_interior_missing(self):
        r=self.run_case(['2026-10-26T00:10:00+00:00'])
        self.assertEqual(r['missing_open_minutes'],0)
        self.assertEqual(r['edge_open_minutes_outside_observed_horizon'],239)
        self.assertEqual(r['h4_aggregation']['complete_bars'],0)

    def test_naive_duplicate_empty_rejected(self):
        for stamps in ([], ['2026-10-26T00:10:00'], ['2026-10-26T00:10:00+00:00']*2):
            with self.subTest(stamps=stamps), self.assertRaises(ValueError):
                self.run_case(stamps)

if __name__=='__main__': unittest.main()
