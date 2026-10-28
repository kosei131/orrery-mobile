import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from lsr03_tick_study import study_catalog
from lsr04_tick_catalog import save_tick_catalog
from test_lsr02_paths import fixture


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'ticks'
        self.h,self.f,self.m=fixture()
        self.end=self.m[-1]['close_time']
        self.start=105900

    def build(self, quotes, **settings):
        epoch=datetime(1970,1,1,tzinfo=timezone.utc)
        opts=dict(symbol='XAUUSD',start_utc=epoch+timedelta(seconds=self.start),
            end_utc=epoch+timedelta(seconds=self.end),source='SYNTHETIC_STUDY',
            broker_spec=dict(symbol='XAUUSD',point=.01,trade_contract_size=100,digits=2),
            max_spread_points=100,max_gap_seconds=3000,
            windows=[dict(start=epoch+timedelta(seconds=self.start),end=epoch+timedelta(seconds=self.end),count=len(quotes))])
        opts.update(settings)
        self.saved=save_tick_catalog(self.path,[dict(ticks=quotes,audit_options=opts)],
            start_utc=opts['start_utc'],end_utc=opts['end_utc'])

    def q(self,t,bid,ask):return dict(time_msc=t,bid=bid,ask=ask)

    def run_study(self, **kw):
        args=dict(expected_catalog_sha256=self.saved['catalog_sha256'],h4=self.h,m15=self.f,m5=self.m,
            bar_source='SYNTHETIC_STUDY',as_of=self.end,buffer=.1,target_r=2,
            round_trip_cost_per_unit=.1,slippage=0,period=2)
        args.update(kw)
        return study_catalog(self.path,**args)

    def test_existing_candidate_path_connects_to_bid_ask_outcome(self):
        self.build([self.q(105900000,12,12.1),self.q(105900001,12,12.1),self.q(106000000,17,17.1)])
        r=self.run_study();row=r['rows'][0]
        self.assertEqual(len(r['rows']),1)
        self.assertEqual(row['status'],'CLOSED')
        self.assertEqual(row['entry_price'],12.1)
        self.assertGreater(row['entry_at'],row['structural_at']*1000)
        self.assertAlmostEqual(row['net_r'],(17-12.1-.1)/(12.1-9.9))
        self.assertFalse(r['execution_allowed'])
        self.assertFalse(r['market_edge_verified'])
        self.assertFalse(r['bar_provenance_verified'])
        self.assertFalse(r['portfolio_metrics_available'])

    def test_closed_outcome_identical_for_passed_and_filtered(self):
        self.build([self.q(105900001,12,12.1),self.q(106000000,17,17.1)])
        low=self.run_study(min_vhf=0);high=self.run_study(min_vhf=1)
        self.assertEqual(low['rows'][0]['net_r'],high['rows'][0]['net_r'])
        self.assertEqual(high['summaries']['LSR02']['closed'],1)
        self.assertEqual(high['summaries']['LSR03']['candidates']+high['summaries']['VHF_FILTERED']['candidates'],1)

    def test_stop_gap_and_cost_recorded_as_loss(self):
        self.build([self.q(105900001,12,12.1),self.q(106000000,8,8.1)])
        row=self.run_study()['rows'][0]
        self.assertEqual(row['exit_reason'],'STOP')
        self.assertEqual(row['exit_price'],8)
        self.assertLess(row['net_r'],-1)

    def test_open_trade_not_counted_as_win(self):
        self.build([self.q(105900001,12,12.1),self.q(106000000,12.5,12.6)])
        r=self.run_study()
        self.assertEqual(r['rows'][0]['status'],'OPEN')
        self.assertEqual(r['summaries']['LSR02']['closed'],0)
        self.assertIsNone(r['summaries']['LSR02']['expectancy_r'])

    def test_cost_can_turn_price_profit_into_net_loss(self):
        self.build([self.q(105900001,12,12.1),self.q(106000000,17,17.1)])
        self.assertLess(self.run_study(round_trip_cost_per_unit=6)['rows'][0]['net_r'],0)

    def test_no_post_signal_quote_is_not_a_fill(self):
        self.build([self.q(105900000,12,12.1)])
        r=self.run_study()
        self.assertEqual(r['rows'][0]['status'],'NO_ENTRY_QUOTE')
        self.assertEqual(r['summaries']['LSR02']['not_filled'],1)

    def test_source_mismatch_and_wrong_end_rejected(self):
        self.build([self.q(105900001,12,12.1)])
        with self.assertRaises(ValueError):self.run_study(bar_source='OTHER')
        with self.assertRaises(ValueError):self.run_study(as_of=self.end-1)

    def test_bad_ticks_block_outcomes(self):
        self.build([self.q(105900001,12,12.1),self.q(106000000,0,1)])
        r=self.run_study()
        self.assertEqual(r['status'],'BLOCKED_GLOBAL_TICK_QUALITY')
        self.assertEqual(r['rows'],[])

    def test_unexplained_global_silence_blocks(self):
        self.build([self.q(105900001,12,12.1)],max_gap_seconds=60)
        self.assertEqual(self.run_study()['status'],'BLOCKED_GLOBAL_TICK_QUALITY')

    def test_strict_delay_and_work_budget(self):
        self.build([self.q(105900001,12,12.1),self.q(106000000,17,17.1)])
        with self.assertRaises(ValueError):self.run_study(entry_delay_msc=0)
        with self.assertRaises(ValueError):self.run_study(max_candidate_tick_visits=1)
        with self.assertRaises(ValueError):self.run_study(max_ticks=1)

    def test_no_structure_produces_no_fabricated_trade(self):
        self.build([self.q(105900001,12,12.1)])
        for bar in self.h:bar.update(open=12,close=12,high=13,low=11)
        r=self.run_study()
        self.assertEqual(r['rows'],[])
        self.assertEqual(r['summaries']['LSR02']['closed'],0)

    def test_sell_uses_bid_entry_ask_exit(self):
        self.h,self.f,self.m=fixture(True)
        self.build([self.q(105900001,17.9,18),self.q(106000000,12.9,13)])
        row=self.run_study()['rows'][0]
        self.assertEqual(row['side'],'SELL')
        self.assertEqual(row['entry_price'],17.9)
        self.assertEqual(row['exit_price'],13)

    def test_gap_across_chunks_cannot_hide_below_each_edge_threshold(self):
        epoch=datetime(1970,1,1,tzinfo=timezone.utc)
        mid=self.start+1050
        chunks=[]
        for a,b,q in ((self.start,mid,self.q(105900001,12,12.1)),
                      (mid,self.end,self.q(107900000,12,12.1))):
            start=epoch+timedelta(seconds=a);end=epoch+timedelta(seconds=b)
            options=dict(symbol='XAUUSD',start_utc=start,end_utc=end,
                source='SYNTHETIC_STUDY',broker_spec=dict(symbol='XAUUSD',point=.01,trade_contract_size=100,digits=2),
                max_spread_points=100,max_gap_seconds=1200,windows=[dict(start=start,end=end,count=1)])
            chunks.append(dict(ticks=[q],audit_options=options))
        self.saved=save_tick_catalog(self.path,chunks,start_utc=epoch+timedelta(seconds=self.start),
            end_utc=epoch+timedelta(seconds=self.end))
        r=self.run_study()
        self.assertEqual(r['status'],'BLOCKED_GLOBAL_TICK_QUALITY')
        self.assertGreater(r['audit']['observed_max_gap_seconds'],1200)
        self.assertEqual(r['integrity']['blocked_quality_chunks'],0)


if __name__=='__main__':unittest.main()
