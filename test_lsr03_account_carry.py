import unittest
from datetime import datetime,timezone
from lsr03_account_replay import replay_account

BOUNDARY=int(datetime(2026,10,28,10,tzinfo=timezone.utc).timestamp()*1000)
ENTRY=BOUNDARY-1000


def q(at,bid=100,ask=100.1):return dict(time_msc=at,bid=bid,ask=ask)

def plan():
    return dict(id='carry',symbol='XAUUSD',side='BUY',known_at_msc=ENTRY-1,
        eligible_after_msc=ENTRY,expires_at_msc=BOUNDARY+10000,stop=99,target=102)

def pnl(symbol,side,lots,entry,exit_price,at):return (exit_price-entry)*lots*(1 if side=='BUY' else -1)


class CarryTests(unittest.TestCase):
    def run_account(self,quotes,carry=None,**kw):
        args=dict(symbol='XAUUSD',volume_min=.01,volume_max=100,volume_step=.01,
            pnl_quote=pnl,round_trip_cost_per_lot_usd=.1,cost_source='SYNTHETIC_FEE',
            slippage=0,carry_quote=carry if carry is not None else lambda *a:0,
            carry_source='SYNTHETIC_CUMULATIVE_USD')
        args.update(kw)
        return replay_account(quotes,[plan()],**args)

    def test_exact_boundary_equity_includes_floating_and_cost_once(self):
        carry=lambda symbol,side,lots,entry,at:2 if at>=BOUNDARY else 0
        r=self.run_account([q(ENTRY),q(BOUNDARY,100.5,100.6),q(BOUNDARY+1000,102,102.1)],carry)
        lots=r['decisions'][0]['lots'];fee=.1*lots
        self.assertAlmostEqual(r['daily_snapshots'][1]['starting_equity_usd'],3000-fee-2+.4*lots)
        self.assertEqual(r['daily_snapshots'][1]['method'],'EXACT_BOUNDARY_QUOTE')
        self.assertAlmostEqual(r['ending_balance_usd'],3000+(102-100.1)*lots-fee-2)
        self.assertEqual(r['carry_cost_usd'],2)
        self.assertEqual(r['trades'][0]['carry_cost_usd'],2)
        self.assertFalse(r['six_month_backtest_complete'])

    def test_repeated_cumulative_charge_not_applied_twice(self):
        carry=lambda symbol,side,lots,entry,at:3 if at>=BOUNDARY else 0
        r=self.run_account([q(ENTRY),q(BOUNDARY),q(BOUNDARY+1),q(BOUNDARY+2),q(BOUNDARY+3,102,102.1)],carry)
        self.assertEqual(r['carry_cost_usd'],3)
        self.assertEqual(r['trades'][0]['cost'],r['trades'][0]['lots']*.1+3)

    def test_swap_credit_kept_as_income_not_dropped(self):
        carry=lambda symbol,side,lots,entry,at:-2 if at>=BOUNDARY else 0
        r=self.run_account([q(ENTRY),q(BOUNDARY),q(BOUNDARY+1,102,102.1)],carry)
        trade=r['trades'][0]
        self.assertEqual(r['carry_cost_usd'],-2)
        self.assertAlmostEqual(trade['gross_pnl'],trade['price_gross_pnl_usd']+2)
        self.assertAlmostEqual(r['ending_balance_usd']-3000,trade['net_usd'])

    def test_later_quote_is_never_used_as_boundary_price(self):
        r=self.run_account([q(ENTRY),q(BOUNDARY+1000,101,101.1)],boundary_quote_max_age_msc=1000)
        snapshot=r['daily_snapshots'][1];lots=r['decisions'][0]['lots']
        self.assertEqual(snapshot['quote_time_msc'],ENTRY)
        self.assertEqual(snapshot['method'],'LAST_OBSERVED_BEFORE_BOUNDARY')
        self.assertAlmostEqual(snapshot['starting_equity_usd'],3000-.1*lots-.1*lots)

    def test_missing_or_stale_boundary_quote_blocks(self):
        with self.assertRaisesRegex(ValueError,'boundary quote'):
            self.run_account([q(ENTRY),q(BOUNDARY+1000)])
        with self.assertRaisesRegex(ValueError,'boundary quote'):
            self.run_account([q(ENTRY),q(BOUNDARY+1000)],boundary_quote_max_age_msc=999)

    def test_multiple_unobserved_boundaries_block(self):
        with self.assertRaisesRegex(ValueError,'intervening'):
            self.run_account([q(ENTRY),q(BOUNDARY+86400000)])

    def test_missing_nonfinite_or_nonzero_entry_carry_blocks(self):
        for carry in (lambda *a:None,lambda *a:float('nan'),lambda *a:1):
            with self.assertRaises(ValueError):self.run_account([q(ENTRY)],carry)
        with self.assertRaises(ValueError):
            self.run_account([q(ENTRY)],carry_source=None)

    def test_carry_cost_on_new_day_can_trigger_daily_stop(self):
        carry=lambda symbol,side,lots,entry,at:40 if at>BOUNDARY else 0
        r=self.run_account([q(ENTRY),q(BOUNDARY),q(BOUNDARY+1000)],carry)
        self.assertTrue(r['daily_stop_held'])
        self.assertEqual(r['carry_cost_usd'],40)
        self.assertEqual(r['closed_statistics']['trades'],0)
        self.assertIsNotNone(r['open_position'])

    def test_boundary_swap_and_stop_same_quote_reconciles(self):
        carry=lambda symbol,side,lots,entry,at:2 if at>=BOUNDARY else 0
        r=self.run_account([q(ENTRY),q(BOUNDARY,98,98.1)],carry)
        self.assertEqual(len(r['trades']),1)
        self.assertEqual(r['trades'][0]['exit_reason'],'STOP')
        self.assertAlmostEqual(r['ending_balance_usd']-3000,r['trades'][0]['net_usd'])
        self.assertEqual(r['carry_cost_usd'],2)

    def test_later_carry_cannot_change_prior_lot_size(self):
        first=self.run_account([q(ENTRY)])
        charged=self.run_account([q(ENTRY),q(BOUNDARY)],
            lambda symbol,side,lots,entry,at:20 if at>=BOUNDARY else 0)
        self.assertEqual(first['decisions'][0]['lots'],charged['decisions'][0]['lots'])

    def test_open_balance_includes_fee_and_carry_but_no_closed_win(self):
        r=self.run_account([q(ENTRY),q(BOUNDARY)],
            lambda symbol,side,lots,entry,at:2 if at>=BOUNDARY else 0)
        lots=r['decisions'][0]['lots']
        self.assertAlmostEqual(r['ending_balance_usd'],3000-.1*lots-2)
        self.assertEqual(r['closed_trade_net_usd'],0)
        self.assertEqual(r['open_position']['carry'],2)

    def test_carry_timeline_invoked_chronologically(self):
        seen=[]
        def carry(symbol,side,lots,entry,at):
            seen.append(at);return 0
        self.run_account([q(ENTRY),q(BOUNDARY+500)],carry,boundary_quote_max_age_msc=1000)
        self.assertEqual(seen,sorted(seen))
        self.assertIn(BOUNDARY,seen)
        self.assertIn(BOUNDARY+500,seen)

    def test_missing_carry_at_later_boundary_never_becomes_zero(self):
        def missing(symbol,side,lots,entry,at):return 0 if at<BOUNDARY else None
        with self.assertRaises(ValueError):
            self.run_account([q(ENTRY),q(BOUNDARY)],missing)

    def test_changed_carry_at_same_boundary_clock_blocks(self):
        calls=0
        def revised(symbol,side,lots,entry,at):
            nonlocal calls
            if at<BOUNDARY:return 0
            calls+=1;return calls
        with self.assertRaisesRegex(ValueError,'same observation clock'):
            self.run_account([q(ENTRY),q(BOUNDARY)],revised)


if __name__=='__main__':unittest.main()
