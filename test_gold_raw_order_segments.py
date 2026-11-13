import unittest
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import zipfile
from orrery_gold_raw_order_segments import analyze

class GoldRawSegmentsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'gold.zip'
        self.now=datetime(2026,11,3,tzinfo=timezone.utc)

    def make(self, rows):
        with zipfile.ZipFile(self.path,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('DAT_ASCII_XAUUSD_T_202610.csv',''.join(
                t+',4000.0,4000.5,0\n' for t in rows))
        return sha256(self.path.read_bytes()).hexdigest()

    def run_scan(self, rows):
        pin=self.make(rows)
        return analyze(self.path,expected_sha256=pin,month='202610',now=self.now)

    def test_split_clock_reversal_and_large_gap_without_sorting(self):
        r=self.run_scan(['20261001 000000000','20261001 000001000',
                         '20261001 000000000','20261001 000200000'])
        self.assertEqual(r['source_ticks'],4)
        self.assertEqual(r['clock_reversal_pairs'],1)
        self.assertEqual(r['gaps_over_60s'],1)
        self.assertEqual(r['segments'],3)
        self.assertEqual([g['quotes'] for g in r['segment_inventory']],[2,1,1])
        self.assertFalse(r['valid_broker_backtest'])
        self.assertIsNone(r['actual_profit_usd'])
        self.assertFalse(r['execution_allowed'])

    def test_same_second_kept_in_one_segment_but_not_order_verified(self):
        r=self.run_scan(['20261001 000000000','20261001 000000000','20261001 000001000'])
        self.assertEqual(r['segments'],1)
        self.assertEqual(r['same_second_adjacent_pairs'],1)
        self.assertFalse(r['verified_execution_chronology'])

    def test_segment_span_summary_does_not_claim_complete_minutes(self):
        r=self.run_scan(['20261001 000000000','20261001 000600000',
                         '20261001 000600000','20261001 002200000'])
        d=r['distribution']
        self.assertEqual(d['spans_at_least_5m'],0)
        self.assertEqual(d['spans_at_least_15m'],0)
        self.assertEqual(d['one_quote_segments'],2)
        self.assertEqual(d['segments_with_same_second_pairs'],1)
        self.assertTrue(d['span_thresholds_are_not_data_completeness'])
        self.assertTrue(d['segment_chronology_is_not_broker_certified'])
        self.assertFalse(r['valid_broker_backtest'])

    def test_unbroken_long_span_is_not_execution_certified(self):
        r=self.run_scan(['20261001 000000000','20261001 000300000'])
        d=r['distribution']
        self.assertEqual(d['spans_at_least_5m'],0)
        self.assertFalse(r['verified_execution_chronology'])

    def test_source_bytes_preserved(self):
        r=self.run_scan(['20261001 000000000'])
        self.assertEqual(r['source_zip_sha256'],sha256(self.path.read_bytes()).hexdigest())
        self.assertFalse(r['quotes_reordered'])
        self.assertFalse(r['bid_ask_bar_exported'])

    def test_wrong_pin_and_future_month_rejected(self):
        self.make(['20261001 000000000'])
        with self.assertRaises(ValueError):
            analyze(self.path,expected_sha256='0'*64,month='202610',now=self.now)
        with self.assertRaises(ValueError):
            analyze(self.path,expected_sha256=sha256(self.path.read_bytes()).hexdigest(),month='202611',now=self.now)

    def test_crossed_quote_rejected(self):
        with zipfile.ZipFile(self.path,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('DAT_ASCII_XAUUSD_T_202610.csv','20261001 000000000,4001,4000,0\n')
        with self.assertRaises(ValueError):
            analyze(self.path,expected_sha256=sha256(self.path.read_bytes()).hexdigest(),month='202610',now=self.now)

if __name__=='__main__':
    unittest.main()
