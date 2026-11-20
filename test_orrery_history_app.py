import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import mt5_local_dashboard as dashboard
from orrery_history_app import frames, snapshot, coverage, crosscheck, session_review
from lsr02_overlay_export import overlay


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
        for label,step in [('M5',300),('M15',900),('H4',14400)]:
            with (self.folder/f'XAUUSD_{label}_UNVERIFIED_QUOTE.csv').open('w',newline='',encoding='utf-8') as stream:
                writer=csv.writer(stream)
                writer.writerow(['timestamp_utc','bid_open','bid_high','bid_low','bid_close'])
                for i in range(100):
                    writer.writerow([datetime.fromtimestamp(i*step,timezone.utc).isoformat(),100,102,99,101])

    def test_history_uses_real_csv_without_demo_or_account_claims(self):
        result=snapshot(self.folder)
        self.assertEqual(result['status'],'PUBLIC_HISTORY_RESEARCH')
        self.assertIsNone(result['balance'])
        self.assertEqual(len(result['charts']),3)
        self.assertTrue(all(c['indicators']['atr'] is not None for c in result['analysis']['charts']))
        with patch.object(dashboard,'HISTORY_SNAPSHOT',result),patch.object(dashboard,'mt5') as mt5:
            display=dashboard.snapshot()
            self.assertEqual({k:v for k,v in display.items() if k!='prospective_readiness'},result)
            self.assertFalse(display['prospective_readiness']['data_acquired'])
            self.assertIsNone(display['prospective_readiness']['prospective_candidates'])
            mt5.initialize.assert_not_called()

    def test_coverage_counts_gaps_without_filling(self):
        data=frames(self.folder);data['5m'].pop(20)
        report=coverage(data)['5m']
        self.assertEqual(report['rows'],99)
        self.assertEqual(report['gap_count'],1)
        self.assertEqual(report['longest_contiguous_bars'],79)

    def test_bad_ohlc_rejected(self):
        p=self.folder/'XAUUSD_M5_UNVERIFIED_QUOTE.csv'
        p.write_text(p.read_text().replace(',100,102,99,101',',100,102,103,101'),encoding='utf-8')
        with self.assertRaises(ValueError):frames(self.folder)

    def test_public_provenance_cannot_be_claimed_as_verified(self):
        with self.assertRaisesRegex(ValueError,'provenance'):
            overlay([],symbol='XAUUSD',interval=300,as_of=0,tenkan=9,kijun=26,
                span_b=52,shift=26,source='PUBLIC_UNVERIFIED_OHLC',source_verified=True)

    def test_crosscheck_rejects_missing_minutes_and_changed_parent(self):
        source=self.folder/'source.csv'
        source.write_text('datetime,open,high,low,close\n'+''.join(
            f'1970-01-01T00:0{i}:00+00:00,100,102,99,101\n' for i in range(5)),encoding='utf-8')
        data={'5m':[dict(close_time=300,open=100,high=102,low=99,close=101)]}
        self.assertEqual(crosscheck(source,data)['5m']['checked_parents'],1)
        data['5m'][0]['high']=103
        with self.assertRaisesRegex(ValueError,'OHLC'):crosscheck(source,data)
        data['5m'][0]['high']=102
        source.write_text(source.read_text().replace('1970-01-01T00:02:00+00:00,100,102,99,101\n',''),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'missing M1'):crosscheck(source,data)


class SessionReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source.csv'
        self.normalized=self.root/'XAUUSD_M1_UNVERIFIED_QUOTE.csv'
        self.output=self.root/'new_session_review'

    def write(self, offsets):
        base=datetime(2026,10,26,20,tzinfo=timezone.utc)
        with self.source.open('w',newline='') as a,self.normalized.open('w',newline='') as b:
            left=csv.writer(a);right=csv.writer(b)
            left.writerow(['datetime','open','high','low','close'])
            right.writerow(['timestamp_utc','bid_open','bid_high','bid_low','bid_close'])
            for minute in offsets:
                row=[(base+timedelta(minutes=minute)).isoformat(),100,102,99,101]
                left.writerow(row);right.writerow(row)

    def test_opt_in_partial_bars_remain_separate_and_unverified(self):
        self.write([m for m in range(240) if m<60 or m>=120])
        r=session_review(self.source,self.root,self.output)
        self.assertEqual(r['normalized_source_rows_matched'],180)
        self.assertEqual(r['h4_aggregation']['complete_session_partial_bars'],1)
        self.assertFalse(r['baseline_bars_replaced'])
        self.assertFalse(r['strategy_comparison_executed'])
        self.assertFalse(r['h4_strategy_ready'])
        self.assertIsNone(r['actual_profit_usd'])
        import json
        self.assertEqual(json.loads((self.output/'report.json').read_text()),r)

    def test_changed_normalized_price_rejected_before_export(self):
        self.write(range(5))
        self.normalized.write_text(self.normalized.read_text().replace(',102,',',103,',1))
        with self.assertRaisesRegex(ValueError,'OHLC mismatch'):
            session_review(self.source,self.root,self.output)
        self.assertFalse(self.output.exists())

    def test_missing_normalized_row_rejected_before_export(self):
        self.write(range(5))
        self.normalized.write_text('\n'.join(self.normalized.read_text().splitlines()[:-1])+'\n')
        with self.assertRaisesRegex(ValueError,'row count'):
            session_review(self.source,self.root,self.output)
        self.assertFalse(self.output.exists())

    def test_observed_closure_quote_blocks_session_export(self):
        self.write([60])
        r=session_review(self.source,self.root,self.output)
        self.assertEqual(r['quotes_during_published_closure'],1)
        self.assertIsNone(r['h4_aggregation'])
        self.assertFalse((self.output/'H4_WEEKLY_SCHEDULE_UNVERIFIED.csv').exists())

    def test_existing_output_is_preserved(self):
        self.write(range(5));self.output.mkdir()
        kept=self.output/'keep.txt';kept.write_text('keep')
        with self.assertRaises(FileExistsError):session_review(self.source,self.root,self.output)
        self.assertEqual(kept.read_text(),'keep')
