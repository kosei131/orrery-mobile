import unittest
from copy import deepcopy
from lsr03_account_study import build_account_plans, compare_catalog_accounts
from lsr03_account_replay import replay_account
from lsr03_adapter import compare_vhf, collect_retests
import test_lsr03_tick_study as fixtures
import test_lsr03_account_replay as account_fixtures


class AccountStudyTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.StudyTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def compare(self, **kw):
        f=self.fixture
        args=dict(expected_catalog_sha256=f.saved['catalog_sha256'],h4=f.h,m15=f.f,m5=f.m,
            bar_source='SYNTHETIC_STUDY',as_of=f.end,buffer=.1,target_r=2,
            volume_min=.01,volume_max=100,volume_step=.01,pnl_quote=account_fixtures.pnl,
            round_trip_cost_per_lot_usd=.01,cost_source='SYNTHETIC_USD_MODEL',slippage=0,
            period=2,min_vhf=0)
        args.update(kw)
        return compare_catalog_accounts(f.path,**args)

    def test_detected_candidate_reaches_actual_account_decision(self):
        f=self.fixture
        f.build([f.q(105900001,12,12.1),f.q(106000000,20,20.1)])
        r=self.compare();base=r['accounts']['LSR02']
        self.assertEqual(r['status'],'MATCHED_INTRADAY_ACCOUNT_RESEARCH')
        self.assertEqual(len(base['trades']),1)
        self.assertEqual(base['decisions'][0]['status'],'RESEARCH_ENTRY')
        self.assertLessEqual(base['decisions'][0]['planned_risk_usd'],7.5+1e-8)
        self.assertEqual(base['initial_equity_usd'],3000)
        self.assertEqual(r['accounts']['LSR03']['initial_equity_usd'],3000)
        self.assertFalse(r['market_edge_verified'])
        self.assertFalse(r['six_month_backtest_complete'])
        self.assertFalse(r['execution_allowed'])

    def test_target_uses_only_confirmed_close_and_original_stop(self):
        f=self.fixture
        full=build_account_plans('XAUUSD',f.h,f.f,f.m,as_of=f.end,buffer=.1,target_r=2,period=2,min_vhf=0)
        plan=full['plans'][0];close=next(b['close'] for b in f.m if b['close_time']*1000==plan['known_at_msc'])
        self.assertAlmostEqual(plan['target'],close+2*(close-plan['stop']))
        self.assertEqual(plan['stop'],9.9)
        self.assertNotIn('net_r',plan)
        self.assertNotIn('invalid_at',plan)

    def test_prefix_invariance_of_entry_plans(self):
        f=self.fixture
        full=build_account_plans('XAUUSD',f.h,f.f,f.m,as_of=f.end,buffer=.1,target_r=2,period=2,min_vhf=0)
        for t in (105600,105900,106200):
            prefix=build_account_plans('XAUUSD',[b for b in f.h if b['close_time']<=t],
                [b for b in f.f if b['close_time']<=t],[b for b in f.m if b['close_time']<=t],
                as_of=t,buffer=.1,target_r=2,period=2,min_vhf=0)
            self.assertEqual(prefix['plans'],[p for p in full['plans'] if p['known_at_msc']<=t*1000])

    def test_no_retroactive_target_change_for_different_later_ticks(self):
        f=self.fixture
        f.build([f.q(105900001,12,12.1),f.q(106000000,20,20.1)])
        r=self.compare()
        compiled=build_account_plans('XAUUSD',f.h,f.f,f.m,as_of=f.end,buffer=.1,target_r=2,period=2,min_vhf=0)
        self.assertEqual(r['plans'],compiled['plans'])

    def test_vhf_exclusion_does_not_share_baseline_capital(self):
        f=self.fixture
        f.build([f.q(105900001,12,12.1),f.q(106000000,20,20.1)])
        r=self.compare(min_vhf=1)
        self.assertGreater(r['accounts']['LSR02']['ending_balance_usd'],3000)
        self.assertEqual(r['accounts']['LSR03']['ending_balance_usd'],3000)
        self.assertEqual(r['candidate_counts']['VHF_FILTERED'],1)

    def test_unfinished_position_excluded_from_closed_profit(self):
        f=self.fixture
        f.build([f.q(105900001,12,12.1),f.q(106000000,12.5,12.6)])
        r=self.compare();base=r['accounts']['LSR02']
        self.assertEqual(len(base['trades']),0)
        self.assertIsNotNone(base['open_position'])
        self.assertEqual(base['closed_trade_net_usd'],0)

    def test_bad_global_quotes_do_not_reach_account_engine(self):
        f=self.fixture
        f.build([f.q(105900001,0,1)])
        r=self.compare()
        self.assertEqual(r['status'],'BLOCKED_GLOBAL_TICK_QUALITY')
        self.assertIsNone(r['accounts'])

    def test_bar_source_mismatch_rejected(self):
        f=self.fixture;f.build([f.q(105900001,12,12.1)])
        with self.assertRaises(ValueError):self.compare(bar_source='OTHER')

    def test_aligned_collector_rejects_mismatched_trace(self):
        f=self.fixture
        compared=compare_vhf('XAUUSD',f.h,f.f,f.m,as_of=f.end,buffer=.1,period=2)
        altered=deepcopy(compared);altered['vhf_trace'][0]['at']+=1
        with self.assertRaises(ValueError):collect_retests(altered,'XAUUSD')

    def test_too_late_delay_does_not_create_fill(self):
        f=self.fixture
        compiled=build_account_plans('XAUUSD',f.h,f.f,f.m,as_of=f.end,
            buffer=.1,target_r=2,period=2,entry_delay_msc=10000000)
        self.assertEqual(compiled['plans'],[])
        self.assertEqual(len(compiled['omitted']),1)


class CancellationTests(unittest.TestCase):
    def replay(self,quotes,cancellations):
        return replay_account(quotes,[account_fixtures.plan()],symbol='XAUUSD',
            volume_min=.01,volume_max=100,volume_step=.01,pnl_quote=account_fixtures.pnl,
            round_trip_cost_per_lot_usd=0,cost_source='SYNTHETIC_USD',slippage=0,
            cancellations=cancellations)

    def test_invalidation_observed_before_first_quote_cancels(self):
        cancel=[dict(id='a',known_at_msc=account_fixtures.T+500)]
        r=self.replay([account_fixtures.q(1000)],cancel)
        self.assertEqual(r['decisions'][0]['reason'],'INVALIDATED_BEFORE_FILL')
        self.assertEqual(r['trades'],[])

    def test_later_invalidation_does_not_retroactively_remove_entry(self):
        quotes=[account_fixtures.q(1),account_fixtures.q(2000,102,102.1)]
        canceled=self.replay(quotes,[dict(id='a',known_at_msc=account_fixtures.T+1000)])
        base=self.replay(quotes,[])
        self.assertEqual(canceled['trades'],base['trades'])
        self.assertEqual(canceled['decisions'],base['decisions'])

    def test_bad_cancellation_clock_or_identity_rejected(self):
        for event in (dict(id='missing',known_at_msc=account_fixtures.T),
                      dict(id='a',known_at_msc=account_fixtures.T-1)):
            with self.assertRaises(ValueError):self.replay([account_fixtures.q(1)],[event])


if __name__=='__main__':unittest.main()
