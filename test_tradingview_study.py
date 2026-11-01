import csv
import io
import tempfile
import unittest
from pathlib import Path
import test_lsr03_account_study as fixture
import test_lsr03_account_replay as account_fixture
from lsr04_tick_archive import _encode
from orrery_tradingview_study import study,prepare,verify


def export(bars,interval):
    s=io.StringIO();w=csv.writer(s);w.writerow(['time','open','high','low','close'])
    for b in bars:w.writerow([b['close_time']-interval,*(b[k] for k in ('open','high','low','close'))])
    return s.getvalue().encode()

class StudyTests(unittest.TestCase):
    def setUp(self):
        f=fixture.AccountStudyTests();f.setUp();self.f=f.fixture;self.addCleanup(f.doCleanups)
        f=self.f
        self.raw={name:export(bars,seconds) for name,bars,seconds in (('H4',f.h,14400),('M15',f.f,900),('M5',f.m,300))}
        self.settings=dict(symbol='XAUUSD',data_source='SYNTHETIC_STUDY',chart_type='STANDARD',price_basis='UNKNOWN',
            time_format='UNIX_SECONDS',column_map={k:k for k in ('time','open','high','low','close')},as_of_s=f.end,
            strategy=dict(buffer=.1,target_r=2,period=2,min_vhf=0,left=1,right=1,lifetime=6000))
    def test_current_strategy_plans_without_quotes_never_invent_profit(self):
        r=study(self.raw,self.settings)
        self.assertEqual(len(r['plans']['plans']),1);self.assertIsNone(r['verified_profit_usd'])
        self.assertIsNone(r['modelled_account_summary']);self.assertFalse(r['execution_allowed'])
        self.assertIn('HALFTREND05',r['excluded_modules'])
    def test_optional_pinned_bid_ask_account_returns_match_existing_engine(self):
        f=self.f;f.build([f.q(105900001,12,12.1),f.q(106000000,20,20.1)])
        opts=dict(path=f.path,expected_catalog_sha256=f.saved['catalog_sha256'],volume_min=.01,volume_max=100.,volume_step=.01,
            pnl_quote=account_fixture.pnl,round_trip_cost_per_lot_usd=.01,cost_source='SYNTHETIC_USD_MODEL',slippage=0.)
        r=study(self.raw,self.settings,account_inputs=opts)
        self.assertGreater(r['modelled_account_summary']['LSR02']['closed_trade_net_usd'],0)
        native=fixture.AccountStudyTests();native.fixture=f;expected=native.compare()
        for name,summary in r['modelled_account_summary'].items():
            self.assertEqual(summary,{k:expected['accounts'][name][k] for k in summary})
        self.assertEqual(r['modelled_account_summary']['LSR03']['initial_equity_usd'],3000)
        self.assertIsNone(r['verified_profit_usd']);self.assertFalse(r['six_month_backtest_complete'])
    def test_missing_bar_blocks_without_session_invention(self):
        raw=dict(self.raw);raw['M5']=export(self.f.m[:2]+self.f.m[3:],300)
        r=study(raw,self.settings);self.assertEqual(r['status'],'BLOCKED_SESSION_OR_HISTORY_GAPS')
        self.assertIsNone(r['plans']);self.assertIsNone(r['modelled_account_summary'])
    def test_large_gapped_import_reports_all_blockers_and_range(self):
        raw={}
        for frame,interval in (('M5',300),('M15',900),('H4',14400)):
            bars=[dict(close_time=100000+i*interval*2+interval,open=12,high=13,low=11,close=12) for i in range(5000)]
            raw[frame]=export(bars,interval)
        r=study(raw,dict(self.settings,as_of_s=200000000))
        ready=r['import_readiness']
        self.assertEqual(len(ready['blockers']),6)
        self.assertEqual(ready['shared_range_start_s'],100000)
        self.assertEqual(ready['shared_range_end_s'],100000+9999*300)
        self.assertFalse(ready['shared_range_is_gap_free_verified'])
        self.assertEqual(r['audit']['H4']['contiguous_segment_count'],5000)
        self.assertEqual(r['audit']['H4']['longest_contiguous_rows'],1)
        self.assertIsNone(r['verified_profit_usd']);self.assertIsNone(r['plans'])
    def test_nonoverlapping_histories_do_not_compile_strategy(self):
        raw={}
        for frame,start,interval in (('M5',0,300),('M15',10000,900),('H4',100000,14400)):
            raw[frame]=export([dict(close_time=start+(i+1)*interval,open=12,high=13,low=11,close=12) for i in range(2)],interval)
        r=study(raw,dict(self.settings,as_of_s=200000))
        self.assertEqual(r['status'],'BLOCKED_NO_SHARED_TIME_RANGE')
        self.assertIsNone(r['import_readiness']['shared_range_start_s'])
        self.assertEqual(r['import_readiness']['shared_range_seconds'],0)
        self.assertIsNone(r['plans'])
    def test_gap_before_excluded_unfinished_tail_is_not_history_gap(self):
        raw=dict(self.raw)
        raw['M5']+=f"{self.f.end+600},12,13,11,12\r\n".encode()
        r=study(raw,dict(self.settings,as_of_s=self.f.end+600))
        self.assertEqual(r['audit']['M5']['deferred_unconfirmed_rows'],1)
        self.assertEqual(r['audit']['M5']['gap_count'],0)
        self.assertEqual(r['audit']['M5']['contiguous_segment_count'],1)
    def test_duplicate_and_nonfinite_rows_rejected(self):
        raw=dict(self.raw);raw['M5']+=raw['M5'].splitlines()[-1]+b'\n'
        with self.assertRaises(ValueError):study(raw,self.settings)
        raw=dict(self.raw)
        # Guaranteed nonfinite cell independently of fixture numeric formatting.
        lines=self.raw['M5'].splitlines();cells=lines[1].split(b',');cells[1]=b'NaN';lines[1]=b','.join(cells);raw['M5']=b'\n'.join(lines)
        with self.assertRaises(ValueError):study(raw,self.settings)
    def test_nonstandard_and_ambiguous_time_refused(self):
        with self.assertRaises(ValueError):study(self.raw,dict(self.settings,chart_type='HEIKIN_ASHI'))
        raw={k:v.replace(v.splitlines()[1].split(b',')[0],b'2026-01-01T00:00:00') for k,v in self.raw.items()}
        with self.assertRaises(ValueError):study(raw,dict(self.settings,time_format='ISO8601'))
    def test_trailing_unconfirmed_bar_is_excluded(self):
        raw=dict(self.raw);raw['M5']+=f"{self.f.end},12,13,11,12\r\n".encode()
        r=study(raw,self.settings)
        self.assertEqual(r['audit']['M5']['deferred_unconfirmed_rows'],1)
        self.assertEqual(r['plans'],study(self.raw,self.settings)['plans'])
    def test_optional_account_data_cannot_replace_strategy_inputs(self):
        with self.assertRaises(ValueError):study(self.raw,self.settings,account_inputs={'target_r':10})
    def test_saved_inputs_recompute_and_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);paths={k:root/(k+'.csv') for k in self.raw}
            for k,p in paths.items():p.write_bytes(self.raw[k])
            config=root/'config.json';config.write_bytes(_encode(self.settings));out=root/'run'
            result=prepare(paths,config,out);self.assertTrue(verify(out,result['receipt_sha256'])['recomputed'])
            with self.assertRaises(FileExistsError):prepare(paths,config,out)
            (out/'M5.csv').write_bytes(b'changed')
            with self.assertRaises(ValueError):verify(out,result['receipt_sha256'])
