import ast
import json
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from types import SimpleNamespace as D
from lsr03_mt5_pilot import run_pilot

END=datetime(2026,10,27,8,tzinfo=timezone.utc)


class MT5:
    ACCOUNT_TRADE_MODE_DEMO=0
    COPY_TICKS_ALL=0
    TIMEFRAME_H4=14400
    TIMEFRAME_M15=900
    TIMEFRAME_M5=300
    def __init__(self):self.mode=0;self.login=1;self.reads=0;self.spec_point=.01
    def account_info(self):return D(trade_mode=self.mode,login=self.login,server='FAKE_DEMO',currency='USD')
    def symbol_info(self,symbol):return D(name=symbol,point=self.spec_point,trade_contract_size=100,digits=2)
    def copy_rates_range(self,symbol,frame,start,end):
        self.reads+=1
        return [dict(time=t,open=12,high=12,low=12,close=12)
                for t in range(int(start.timestamp()),int(end.timestamp())+1,frame)]
    def copy_ticks_range(self,symbol,start,end,flags):
        self.reads+=1
        return [dict(time_msc=t*1000,bid=12,ask=12.1)
                for t in range(int(start.timestamp()),int(end.timestamp())+1,30)]


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'run'
        self.config=dict(symbol='XAUUSD',source='SYNTHETIC_DEMO',
            h4_start_utc='2026-10-26T00:00:00+00:00',structure_start_utc='2026-10-27T00:00:00+00:00',
            tick_start_utc='2026-10-27T04:00:00+00:00',end_utc=END.isoformat(),
            chunk_seconds=3600,max_ticks=1000,buffer=.1,target_r=2,
            round_trip_cost_per_unit=.1,slippage=0,cost_assumption_source='SYNTHETIC_ONLY',
            max_spread_points=50,max_gap_seconds=60,period=2,min_vhf=.4)

    def run_pilot(self,mt5=None):
        return run_pilot(mt5 or MT5(),self.config,self.path,now_utc=END+timedelta(hours=1))

    def test_injected_demo_capture_to_report_no_fabricated_trades(self):
        r=self.run_pilot()
        self.assertEqual(r['report_status'],'MATCHED_TICK_CANDIDATE_RESEARCH')
        report=json.loads((self.path/'report.json').read_bytes())
        self.assertEqual(report['rows'],[])
        self.assertEqual(report['summaries']['LSR02']['closed'],0)
        self.assertIsNone(report['summaries']['LSR02']['expectancy_r'])
        self.assertEqual(r['excluded_unfinished_bars'],{'4H':1,'15m':1,'5m':1})
        self.assertTrue((self.path/'run.json').is_file())
        self.assertFalse(r['execution_allowed'])
        self.assertFalse(r['market_edge_verified'])

    def test_live_account_rejected_before_history_reads(self):
        mt5=MT5();mt5.mode=2
        with self.assertRaises(ValueError):self.run_pilot(mt5)
        self.assertEqual(mt5.reads,0)
        self.assertFalse(self.path.exists())

    def test_account_change_during_bar_capture_blocks(self):
        class Changed(MT5):
            def copy_rates_range(self,*args):
                r=super().copy_rates_range(*args);self.login=2;return r
        with self.assertRaises(ValueError):self.run_pilot(Changed())
        self.assertFalse((self.path/'run.json').exists())

    def test_specification_change_during_ticks_blocks(self):
        class Changed(MT5):
            def copy_ticks_range(self,*args):
                r=super().copy_ticks_range(*args);self.spec_point=.001;return r
        with self.assertRaises(ValueError):self.run_pilot(Changed())
        self.assertFalse((self.path/'run.json').exists())

    def test_missing_cost_is_not_defaulted_to_zero(self):
        del self.config['round_trip_cost_per_unit']
        with self.assertRaises(ValueError):self.run_pilot()
        self.assertFalse(self.path.exists())

    def test_unfilled_or_nonfinite_cost_rejected(self):
        for value in (None,float('nan')):
            self.config['round_trip_cost_per_unit']=value
            with self.assertRaises((ValueError,TypeError)):self.run_pilot()
        self.assertFalse(self.path.exists())

    def test_future_or_excessive_horizon_rejected(self):
        self.config['end_utc']=(END+timedelta(days=2)).isoformat()
        with self.assertRaises(ValueError):self.run_pilot()
        self.assertFalse(self.path.exists())

    def test_missing_bars_not_interpolated(self):
        class Gaps(MT5):
            def copy_rates_range(self,*args):
                rows=super().copy_rates_range(*args);return rows[:2]+rows[3:]
        with self.assertRaises(ValueError):self.run_pilot(Gaps())
        self.assertFalse((self.path/'run.json').exists())

    def test_cross_timeframe_inconsistency_blocks(self):
        class Mixed(MT5):
            def copy_rates_range(self,symbol,frame,*args):
                rows=super().copy_rates_range(symbol,frame,*args)
                if frame==900:
                    for row in rows:row.update(open=13,close=13,high=13,low=13)
                return rows
        with self.assertRaisesRegex(ValueError,'Cross-timeframe'):self.run_pilot(Mixed())

    def test_tick_read_failure_no_completion_marker(self):
        class Broken(MT5):
            def copy_ticks_range(self,*args):return None
        with self.assertRaises(ValueError):self.run_pilot(Broken())
        self.assertFalse((self.path/'run.json').exists())

    def test_existing_output_not_overwritten(self):
        self.run_pilot();old=(self.path/'run.json').read_bytes()
        with self.assertRaises(FileExistsError):self.run_pilot()
        self.assertEqual((self.path/'run.json').read_bytes(),old)

    def test_row_budget_does_not_produce_partial_success(self):
        self.config['max_ticks']=1
        with self.assertRaises(ValueError):self.run_pilot()
        self.assertFalse((self.path/'run.json').exists())

    def test_raw_terminal_identifiers_not_saved(self):
        self.run_pilot()
        for name in ('run.json','report.json','settings.json','bars.json'):
            text=(self.path/name).read_text()
            self.assertNotIn('FAKE_DEMO',text)
            self.assertNotIn('"login"',text)
            self.assertNotIn('"password"',text)

    def test_runner_mt5_calls_remain_read_only(self):
        tree=ast.parse(Path('lsr03_mt5_pilot.py').read_text())
        calls={node.func.attr for node in ast.walk(tree) if isinstance(node,ast.Call)
               and isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name)
               and node.func.value.id=='mt5'}
        self.assertLessEqual(calls,{'account_info','symbol_info','copy_rates_range','initialize','shutdown'})
        self.assertIn('copy_rates_range',calls)


if __name__=='__main__':unittest.main()
