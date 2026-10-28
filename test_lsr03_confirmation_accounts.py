import unittest
from unittest.mock import patch
from lsr03_confirmation_accounts import compile_plans, compare_confirmation_accounts
from lsr03_account_replay import replay_account
from lsr04_tick_fills import market_exit_price
from orrery_xau_h4_alignment import START

T=(START+2*86400+12*3600)*1000
C=T//1000

def quote(at,bid=100,ask=100.1):return dict(time_msc=T+at,bid=bid,ask=ask)
def signal():return dict(sweep_close=C-600,confirmation_close=C,side='BUY',poi=dict(low=99,high=101))
def observation(status='RETEST'):
    return dict(sweep_close=C-600,confirmation_close=C,side='BUY',status=status,
                entry_at=C+300 if status=='RETEST' else None)
def refs():return [dict(close_time=C,close=100),dict(close_time=C+300,close=100.5)]
def pnl(symbol,side,lots,entry,close,at):return (close-entry)*lots*(1 if side=='BUY' else -1)
def account(qs,plans,**kw):
    return replay_account(qs,plans,symbol='XAUUSD',volume_min=.01,volume_max=100,
        volume_step=.01,pnl_quote=pnl,round_trip_cost_per_lot_usd=0,
        cost_source='SYNTHETIC_UNIT_TEST_ONLY',slippage=kw.pop('slippage',0),**kw)
def plan(name='a',known=0,side='BUY',limit=1000):
    return dict(id=name,symbol='XAUUSD',side=side,known_at_msc=T+known,
                eligible_after_msc=T+known+1,expires_at_msc=T+known+60000,
                stop=90 if side=='BUY' else 110,target=110 if side=='BUY' else 90,
                max_holding_msc=limit)
def compile_case(**kwargs):
    args=dict(symbol='XAUUSD',fixed_distance=2,target_r=1.5,entry_delay_msc=1,
              entry_window_msc=60000,max_holding_msc=120000)
    args.update(kwargs)
    return compile_plans([signal()],[observation()],refs(),**args)

class HoldingLimitTests(unittest.TestCase):
    def test_timeout_first_observed_quote_includes_closing_side_and_slippage(self):
        for side in ('BUY','SELL'):
            with self.subTest(side=side):
                r=account([quote(1),quote(1001,101,101.2)],[plan(side=side)],slippage=.05)
                t=r['trades'][0]
                self.assertEqual(t['exit_reason'],'TIME_LIMIT')
                self.assertEqual(t['timeout_lag_msc'],0)
                entry=100.15 if side=='BUY' else 99.95
                close=100.95 if side=='BUY' else 101.25
                expected=pnl('XAUUSD',side,t['lots'],entry,close,T+1001)
                self.assertAlmostEqual(t['net_usd'],expected)

    def test_missing_deadline_quote_not_interpolated_and_source_end_stays_open(self):
        r=account([quote(1),quote(5001)],[plan()])
        self.assertEqual(r['trades'][0]['timeout_lag_msc'],4000)
        r=account([quote(1),quote(999)],[plan()])
        self.assertEqual(r['trades'],[])
        self.assertIsNotNone(r['open_position'])

    def test_stop_has_priority_at_deadline_and_no_same_clock_reentry(self):
        r=account([quote(1),quote(1001,89,89.1)],[plan(),plan('b',known=500)])
        self.assertEqual(r['trades'][0]['exit_reason'],'STOP')
        self.assertIsNone(r['trades'][0]['timeout_lag_msc'])
        self.assertEqual(r['decisions'][1]['reason'],'SAME_TIMESTAMP_REENTRY')

    def test_timeout_losses_trigger_existing_three_loss_stop(self):
        qs=[];ps=[]
        for i in range(4):
            at=i*3000
            ps.append(plan(str(i),known=at))
            qs += [quote(at+1),quote(at+1001,99,99.1)]
        r=account(qs,ps)
        self.assertEqual(len(r['trades']),3)
        self.assertTrue(r['streak_stop_held'])
        self.assertEqual(r['decisions'][-1]['reason'],'LATCHED_THREE_LOSS_STOP')

    def test_invalid_holding_limit_and_market_exit_rejected(self):
        for duration in (0,-1,True,1.5):
            with self.subTest(duration=duration),self.assertRaises(ValueError):
                account([quote(1)],[plan(limit=duration)])
        with self.assertRaises(ValueError):market_exit_price(side='BUY',bid=1,ask=2,slippage=2)

class ConfirmationAccountsTests(unittest.TestCase):
    def test_prices_come_from_known_close_and_future_rows_do_not_change_plans(self):
        a=compile_case()
        p=a['modes']['CONFIRMATION']['plans'][0]
        self.assertEqual((p['stop'],p['target']),(98,103))
        self.assertEqual(p['eligible_after_msc'],T+1)
        b=compile_plans([signal()],[observation('EXPIRED')],refs()+[dict(close_time=C+600,close=999)],
            symbol='XAUUSD',fixed_distance=2,target_r=1.5,entry_delay_msc=1,entry_window_msc=60000,max_holding_msc=120000)
        self.assertEqual(a['modes']['CONFIRMATION']['plans'],b['modes']['CONFIRMATION']['plans'])
        self.assertEqual(b['modes']['RETEST']['plans'],[])

    def test_two_accounts_reuse_engine_on_explicit_synthetic_quotes(self):
        qs=[quote(1),quote(120001,100.5,100.6),quote(300001,100.5,100.6),quote(420001,101,101.1)]
        loaded=dict(blocked=False,symbol='XAUUSD',ticks=qs,start_msc=T-1,end_msc=T+500000,audit={})
        with patch('lsr03_confirmation_accounts.load_catalog_ticks',return_value=loaded) as loader:
            r=compare_confirmation_accounts('/synthetic-test',expected_catalog_sha256='TEST',bar_source='SYNTHETIC',
                as_of=(T+500000)/1000,confirmations=[signal()],observations=[observation()],m5=refs(),
                fixed_distance=2,target_r=1.5,entry_delay_msc=1,entry_window_msc=60000,max_holding_msc=120000,
                volume_min=.01,volume_max=100,volume_step=.01,pnl_quote=pnl,
                round_trip_cost_per_lot_usd=0,cost_source='SYNTHETIC_UNIT_TEST_ONLY',slippage=0)
        self.assertEqual(loader.call_count,1)
        self.assertEqual(set(r['accounts']),{'CONFIRMATION','RETEST'})
        for a in r['accounts'].values():
            self.assertEqual(a['initial_equity_usd'],3000)
            self.assertEqual(len(a['trades']),1)
            self.assertEqual(a['trades'][0]['exit_reason'],'TIME_LIMIT')
            self.assertIsNone(a['open_position'])
            self.assertFalse(a['execution_allowed'])

    def test_failed_tick_quality_never_calls_account_engine(self):
        with patch('lsr03_confirmation_accounts.load_catalog_ticks',return_value=dict(blocked=True,audit={'issues':['gap']})), \
             patch('lsr03_confirmation_accounts.replay_account',side_effect=AssertionError('Must not run')):
            r=compare_confirmation_accounts('/test',expected_catalog_sha256='TEST',bar_source='SYNTHETIC',as_of=1,
                confirmations=[],observations=[],m5=[],fixed_distance=2,target_r=1.5,entry_delay_msc=1,
                entry_window_msc=60000,max_holding_msc=120000,volume_min=.01,volume_max=100,volume_step=.01,
                pnl_quote=pnl,round_trip_cost_per_lot_usd=0,cost_source='TEST',slippage=0)
        self.assertIsNone(r['accounts'])
        self.assertEqual(r['status'],'BLOCKED_GLOBAL_TICK_QUALITY')

if __name__=='__main__':unittest.main()
