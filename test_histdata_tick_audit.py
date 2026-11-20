import csv,json,zipfile
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import orrery_histdata_tick_audit as audit


class TickAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.source=self.root/'source.zip';self.now=datetime(2026,11,3,tzinfo=timezone.utc)

    def run_source(self,data,*,mode='STRICT_ORDER',name='DAT_ASCII_USDJPY_T_202610.csv',pin=None):
        with zipfile.ZipFile(self.source,'w',zipfile.ZIP_DEFLATED) as z:z.writestr(name,data)
        pin=pin or sha256(self.source.read_bytes()).hexdigest()
        return audit.audit(self.source,self.root/'out',expected_sha256=pin,symbol='USDJPY',month='202610',now=self.now,mode=mode)

    def test_fixed_est_conversion_uses_no_dst_and_preserves_milliseconds(self):
        t=audit.clock(b'20261001 120000123','202610')
        self.assertEqual(datetime.fromtimestamp(t/1000,timezone.utc).isoformat(),'2026-10-01T17:00:00.123000+00:00')
        self.assertEqual(audit.clock(b'20261001 120000999','202610')-audit.clock(b'20261001 120000001','202610'),998)

    def test_exact_decimal_quotes_ohlc_and_ties_are_preserved(self):
        r=self.run_source('20261001 000000000,150.100,150.105,0\n20261001 000000000,150.102,150.108,0\n20261001 000059999,150.101,150.106,1\n')
        self.assertEqual(r['ticks'],3);self.assertEqual(r['same_timestamp_adjacent_pairs'],1)
        self.assertEqual(r['subsecond_nonzero_ticks'],1);self.assertEqual(r['synchronous_tick_spread_price']['median'],.005)
        with (self.root/'out'/'bid_M1.csv').open() as f:rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),1);self.assertEqual([float(rows[0][k]) for k in ('open','high','low','close')],[150.1,150.102,150.1,150.101])
        self.assertFalse(r['market_session_completeness_verified']);self.assertIsNone(r['win_rate_pct'])

    def test_backwards_clock_fails_strict_but_diagnostic_does_not_export_bars(self):
        text='20261001 000001000,150,150.01,0\n20261001 000000000,150.01,150.02,0\n'
        with self.assertRaisesRegex(ValueError,'ordered historical'):self.run_source(text)
        self.assertFalse((self.root/'out').exists())
        before=sha256(self.source.read_bytes()).hexdigest()
        r=audit.audit(self.source,self.root/'out',expected_sha256=before,symbol='USDJPY',month='202610',now=self.now,mode='DIAGNOSTIC_ONLY')
        self.assertEqual(r['out_of_order_pairs'],1);self.assertEqual(r['maximum_backward_step_msc'],1000)
        self.assertFalse(r['chronological_bar_exported']);self.assertFalse(r['strategy_replay_allowed'])
        self.assertEqual(r['output_sha256'],{});self.assertFalse(list((self.root/'out').glob('*.csv')))
        self.assertEqual(sha256(self.source.read_bytes()).hexdigest(),before)

    def test_missing_minutes_are_not_filled_and_partial_m5_is_rejected(self):
        text=''.join(f'20261001 000{m}00000,150,150.01,0\n' for m in (0,1,3,4))
        r=self.run_source(text)
        self.assertEqual(r['paired_m1_minutes'],4);self.assertEqual(r['missing_internal_minutes'],1)
        self.assertEqual(r['aggregations']['bid_M5']['observed_complete_slot_bars'],0)
        self.assertEqual(r['aggregations']['bid_M5']['rejected_partial_slots'],1)
        self.assertFalse(r['missing_minutes_filled'])

    def test_five_observed_minute_slots_can_aggregate_without_certifying_ticks(self):
        text=''.join(f'20261001 000{m}00000,{150+m/100:.2f},{150.01+m/100:.2f},0\n' for m in range(5))
        r=self.run_source(text)
        self.assertEqual(r['aggregations']['bid_M5']['observed_complete_slot_bars'],1)
        self.assertFalse(r['source_authenticity_verified'])
        self.assertEqual(sum(v['ticks'] for v in r['spread_by_declared_utc_hour'].values()),5)

    def test_wrong_hash_symbol_path_and_future_or_invalid_prices_fail(self):
        good='20261001 000000000,150,150.01,0\n'
        for kwargs in ({'pin':'0'*64},{'name':'DAT_ASCII_XAUUSD_T_202610.csv'},{'name':'../DAT_ASCII_USDJPY_T_202610.csv'}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):self.run_source(good,**kwargs)
        for text in ('20261001 000000000,151,150,0\n','20261001 000000000,150,NaN,0\n',
                     '20261001 000000000,150,151,inf\n','20261001 000000000,150,151,-1\n',
                     '20261101 000000000,150,151,0\n','20261001 000000000;150;151;0\n'):
            with self.subTest(text=text),self.assertRaises(ValueError):self.run_source(text)
        with self.assertRaises(ValueError):audit.price(b'0')

    def test_budgets_and_existing_output_are_not_bypassed(self):
        text='20261001 000000000,150,150.01,0\n20261001 000001000,150,150.01,0\n'
        with patch.object(audit,'MAX_TICKS',1):
            with self.assertRaises(ValueError):self.run_source(text)
        (self.root/'out').mkdir();(self.root/'out'/'keep').write_text('preserve')
        with self.assertRaises(FileExistsError):self.run_source(text)
        self.assertEqual((self.root/'out'/'keep').read_text(),'preserve')

    def test_real_received_archive_evidence_keeps_the_replay_block(self):
        p=Path(__file__).resolve().parent/'research_evidence/local-history-20261101/usdjpy_histdata_tick_audit_20261103.json'
        r=json.loads(p.read_text());self.assertEqual(r['ticks'],2503031)
        self.assertEqual(r['out_of_order_pairs'],341);self.assertEqual(r['maximum_backward_step_msc'],1000)
        self.assertEqual(r['subsecond_nonzero_ticks'],0);self.assertTrue(r['observed_whole_second_timestamps_only'])
        self.assertEqual(r['paired_m1_minutes'],31188);self.assertEqual(r['missing_internal_minutes'],11532)
        self.assertFalse(r['chronological_bar_exported']);self.assertEqual(r['output_sha256'],{})
        self.assertIsNone(r['net_expectancy_r']);self.assertIsNone(r['account_return_pct'])
        self.assertEqual(r['code_sha256'],sha256((p.parents[2]/'orrery_histdata_tick_audit.py').read_bytes()).hexdigest())
