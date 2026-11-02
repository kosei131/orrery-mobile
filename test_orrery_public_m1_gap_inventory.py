import tempfile
import unittest
from pathlib import Path
from orrery_public_m1_gap_inventory import inventory

class PublicM1GapInventoryTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.path=Path(t.name)/'source.csv'

    def write(self, rows):
        self.path.write_text('datetime,open,high,low,close\n'+''.join(
            v+',1,2,0.5,1.5\n' for v in rows),encoding='utf-8')

    def test_detects_gaps_without_calling_them_market_closures(self):
        self.write(['2026-10-30T20:59:00+00:00','2026-10-30T21:00:00+00:00',
            '2026-11-02T00:00:00+00:00','2026-11-02T00:01:00+00:00'])
        a=inventory(self.path)
        self.assertEqual(a['source_rows'],4)
        self.assertEqual(a['gap_count'],1)
        self.assertEqual(a['missing_minute_slots'],3059)
        self.assertTrue(a['gaps'][0]['crosses_weekend'])
        self.assertEqual(a['gaps'][0]['session_reason'],'UNVERIFIED')
        self.assertFalse(a['calendar_authenticated'])
        self.assertFalse(a['backtest_ready'])
        self.assertIsNone(a['actual_profit_usd'])

    def test_rejects_duplicate_reverse_and_nonminute_clock(self):
        for stamps in (
            ['2026-11-01T00:00:00Z','2026-11-01T00:00:00Z'],
            ['2026-11-01T00:01:00Z','2026-11-01T00:00:00Z'],
            ['2026-11-01T00:00:01Z'],
            ['2026-11-01T00:00:00-10:00']):
            with self.subTest(stamps=stamps):
                self.write(stamps)
                with self.assertRaises(ValueError):
                    inventory(self.path)

    def test_complete_three_minutes_have_no_gaps(self):
        self.write(['2026-11-01T00:00:00Z','2026-11-01T00:01:00Z',
                    '2026-11-01T00:02:00Z'])
        a=inventory(self.path)
        self.assertEqual(a['gap_count'],0)
        self.assertEqual(a['missing_minute_slots'],0)
        self.assertFalse(a['continuity_restored'])

if __name__=='__main__':
    unittest.main()
