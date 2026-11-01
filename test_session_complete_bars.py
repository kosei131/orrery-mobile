import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from orrery_m1_complete_bars import aggregate
from orrery_real_bars_lsr_bridge import load

BASE = dt.datetime(2026, 10, 22, tzinfo=dt.timezone.utc)
def iso(m):
    return (BASE + dt.timedelta(minutes=m)).isoformat()
def schedule(parts):
    return {'source': 'TEST calendar, not broker evidence', 'intervals': [
        {'start_utc': iso(a), 'end_utc': iso(b), 'state': state}
        for a, b, state in parts]}

class SessionBarsTests(unittest.TestCase):
    def run_case(self, minutes, calendar, period='H4', price=100):
        with tempfile.TemporaryDirectory() as folder:
            src, dst = Path(folder)/'m1.csv', Path(folder)/'bars.csv'
            with src.open('w', newline='', encoding='utf-8') as fp:
                w = csv.writer(fp)
                w.writerow(['timestamp_utc', 'bid_open', 'bid_high', 'bid_low', 'bid_close'])
                for m in minutes:
                    w.writerow([iso(m), price, price, price, price])
            report = aggregate(src, dst, period, calendar=calendar)
            return report, load(dst, period)

    def test_known_break_keeps_real_partial_h4_without_filling(self):
        cal = schedule([(0, 180, 'OPEN'), (180, 240, 'CLOSED'), (240, 480, 'OPEN')])
        report, result = self.run_case(list(range(180))+list(range(240, 480)), cal)
        self.assertEqual(report['complete_bars'], 2)
        self.assertEqual(report['complete_session_partial_bars'], 1)
        self.assertTrue(result['contiguous'])
        self.assertEqual(result['bars'][0]['close_time'], int(BASE.timestamp())+14400)
        self.assertFalse(report['calendar_broker_verified'])
        self.assertFalse(report['execution_allowed'])
        self.assertTrue(report['no_missing_data_filled'])

    def test_unknown_break_still_rejected(self):
        report, _ = self.run_case(range(180), None)
        self.assertEqual(report['complete_bars'], 0)
        self.assertEqual(report['incomplete_bars_rejected'], 1)

    def test_missing_open_minute_not_excused_by_known_break(self):
        cal = schedule([(0, 180, 'OPEN'), (180, 240, 'CLOSED')])
        report, _ = self.run_case([m for m in range(180) if m != 90], cal)
        self.assertEqual(report['complete_bars'], 0)
        self.assertEqual(report['incomplete_bars_rejected'], 1)

    def test_entire_missing_open_bucket_counted(self):
        report, _ = self.run_case([], schedule([(0, 480, 'OPEN')]))
        self.assertEqual(report['incomplete_bars_rejected'], 2)

    def test_closed_bucket_not_invented_or_bridged(self):
        cal = schedule([(0, 240, 'OPEN'), (240, 480, 'CLOSED'), (480, 720, 'OPEN')])
        report, result = self.run_case(list(range(240))+list(range(480,720)), cal)
        self.assertEqual(report['complete_bars'], 2)
        self.assertFalse(result['contiguous'])

    def test_quote_during_closure_or_outside_horizon_rejected(self):
        for m in (200, 240):
            with self.subTest(m=m), self.assertRaises(ValueError):
                self.run_case([m], schedule([(0, 180, 'OPEN'), (180, 240, 'CLOSED')]))

    def test_calendar_holes_overlap_unknown_state_naive_and_grid_rejected(self):
        cases = [schedule([(0, 60, 'OPEN'), (61, 240, 'CLOSED')]),
                 schedule([(0, 120, 'OPEN'), (60, 240, 'CLOSED')]),
                 schedule([(0, 240, 'UNKNOWN')]), schedule([(1, 240, 'OPEN')]),
                 schedule([(0, 240, 'OPEN')])]
        cases[-1]['intervals'][0]['start_utc'] = '2026-10-22T00:00:00'
        for cal in cases:
            with self.subTest(cal=cal), self.assertRaises(ValueError):
                self.run_case([], cal)

    def test_nonfinite_ohlc_rejected(self):
        for value in (float('inf'), float('nan')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.run_case(range(5), None, 'M5', value)

if __name__ == '__main__':
    unittest.main()
