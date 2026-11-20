from datetime import datetime, timedelta, timezone
from hashlib import sha256
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
        partition=a['weekly_gap_partition']
        self.assertEqual(partition['missing_minutes'],a['missing_minute_slots'])
        self.assertEqual(partition['weekly_open_unexplained_minutes']+
                         partition['weekly_closed_candidate_minutes'],a['missing_minute_slots'])
        self.assertFalse(partition['continuity_restored'])
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

    def test_h4_distinguishes_partial_empty_and_source_edges(self):
        start=datetime(2026,10,1,tzinfo=timezone.utc)
        # Two complete slots, one missing minute, one empty slot; partial edges.
        stamps=[start+timedelta(minutes=i) for i in range(1,1201)
                if i!=500 and not 720<=i<960]
        self.write([t.isoformat() for t in stamps])
        a=inventory(self.path);h=a['h4_source_completeness']
        self.assertEqual(a['source_sha256'],sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(h['complete_interior_slots'],2)
        self.assertEqual(h['missing_h4_slots'],2)
        self.assertEqual(h['m1_slot_classification'],{'partial_1_to_239':1,'empty':1})
        self.assertEqual([x['observed_m1_bars_in_slot'] for x in h['edge_truncated_slots']],[239,1])
        self.assertFalse(h['continuity_restored'])
        self.assertFalse(h['full_h4_rebuild_allowed'])

    def test_exact_h4_boundaries_are_not_truncated(self):
        start=datetime(2026,10,1,tzinfo=timezone.utc)
        self.write([(start+timedelta(minutes=i)).isoformat() for i in range(240)])
        h=inventory(self.path)['h4_source_completeness']
        self.assertEqual(h['complete_interior_slots'],1)
        self.assertEqual(h['edge_truncated_slots'],[])
        self.assertEqual(h['missing_h4_slots'],0)

    def test_rejects_unbounded_sparse_horizon(self):
        self.write(['2024-01-01T00:00:00Z','2026-01-01T00:00:00Z'])
        with self.assertRaisesRegex(ValueError,'horizon'):inventory(self.path)

if __name__=='__main__':
    unittest.main()
