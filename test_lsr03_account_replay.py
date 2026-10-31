import unittest
from datetime import datetime,timezone
from lsr03_account_replay import replay_account

T=int(datetime(2026,10,27,12,tzinfo=timezone.utc).timestamp()*1000)


def q(offset,bid=100,ask=100.1):return dict(time_msc=T+offset,bid=bid,ask=ask)

def plan(name='a',known=0,side='BUY',stop=99,target=102):
    return dict(id=name,symbol='XAUUSD',side=side,known_at_msc=T+known,
        eligible_after_msc=T+known+1,expires_at_msc=T+known+60000,stop=stop,target=target)

def pnl(symbol,side,lots,entry,exit_price,at):
    return (exit_price-entry)*lots*(1 if side=='BUY' else -1)


class AccountTests(unittest.TestCase):
    def run_account(self,quotes,plans=None,**kw):
        args=dict(symbol='XAUUSD',volume_min=.01,volume_max=100,volume_step=.01,
                  pnl_quote=pnl,round_trip_cost_per_lot_usd=0,
                  cost_source='SYNTHETIC_LINEAR_USD_ONLY',slippage=0)
        args.update(kw)
        return replay_account(quotes,[plan()] if plans is None else plans,**args)

    def test_starting_equity_and_cost_inclusive_risk_budget(self):
        r=self.run_account([q(1),q(1000,102,102.1)],round_trip_cost_per_lot_usd=.1)
        self.assertEqual(r['initial_equity_usd'],3000)
        entry=r['decisions'][0]
        self.assertLessEqual(entry['planned_risk_usd'],7.5+1e-8)
        self.assertGreater(r['ending_balance_usd'],3000)
        self.assertEqual(len(r['trades']),1)
        self.assertFalse(r['execution_allowed'])
        self.assertFalse(r['six_month_backtest_complete'])

    def test_lot_sizing_does_not_use_future_profit(self):
        prefix=self.run_account([q(1)])
        win=self.run_account([q(1),q(1000,102,102.1)])
        loss=self.run_account([q(1),q(1000,98,98.1)])
        self.assertEqual(prefix['decisions'][0]['lots'],win['decisions'][0]['lots'])
        self.assertEqual(prefix['decisions'][0]['lots'],loss['decisions'][0]['lots'])

    def test_open_position_marked_not_counted_as_win(self):
        r=self.run_account([q(1),q(1000,99.5,99.6)],round_trip_cost_per_lot_usd=.1)
        self.assertEqual(r['closed_statistics']['trades'],0)
        self.assertIsNotNone(r['open_position'])
        self.assertLess(r['ending_equity_usd'],r['ending_balance_usd'])
        self.assertGreater(r['max_sampled_equity_drawdown_usd'],0)
        self.assertEqual(r['closed_trade_net_usd'],0)

    def test_overlapping_candidate_is_skipped_not_added(self):
        r=self.run_account([q(1),q(1000),q(2000,102,102.1)],
                           [plan(),plan('b',known=500)])
        self.assertEqual(r['decisions'][1]['reason'],'POSITION_ALREADY_OPEN')
        self.assertEqual(len(r['trades']),1)

    def test_three_losses_stop_later_entries(self):
        quotes=[];plans=[]
        for i in range(4):
            at=i*10000;plans.append(plan(str(i),known=at))
            quotes += [q(at+1),q(at+2000,99,99.1)]
        r=self.run_account(quotes,plans)
        self.assertEqual(len(r['trades']),3)
        self.assertTrue(r['streak_stop_held'])
        self.assertEqual(r['decisions'][-1]['reason'],'LATCHED_THREE_LOSS_STOP')

    def test_gap_can_exceed_planned_risk_and_hold_daily_stop(self):
        r=self.run_account([q(1),q(1000,95,95.1),q(2001)],
                           [plan(),plan('b',known=2000)])
        self.assertLess(r['trades'][0]['net_usd'],-30)
        self.assertTrue(r['daily_stop_held'])
        self.assertEqual(r['decisions'][-1]['reason'],'LATCHED_DAILY_STOP')

    def test_floating_breach_latches_even_after_equity_recovers(self):
        def changing_fx(symbol,side,lots,entry,exit_price,at):
            return pnl(symbol,side,lots,entry,exit_price,at)*(10 if at==T+1000 else 1)
        r=self.run_account([q(1),q(1000,99.5,99.6),q(2000,100.2,100.3),q(3000,102,102.1),q(4001)],
            [plan(),plan('b',known=4000)],pnl_quote=changing_fx)
        self.assertGreater(r['ending_balance_usd'],3000)
        self.assertTrue(r['daily_stop_held'])
        self.assertEqual(r['decisions'][-1]['reason'],'LATCHED_DAILY_STOP')
        self.assertGreater(r['max_sampled_equity_drawdown_usd'],30)

    def test_no_same_timestamp_reentry_after_close(self):
        r=self.run_account([q(1),q(1000,102,102.1)],
            [plan(),plan('b',known=500,stop=101,target=104)])
        self.assertEqual(r['decisions'][-1]['reason'],'SAME_TIMESTAMP_REENTRY')

    def test_expired_or_never_eligible_not_filled(self):
        r=self.run_account([q(70000)])
        self.assertEqual(r['decisions'][0]['reason'],'EXPIRED')
        r=self.run_account([q(0)])
        self.assertEqual(r['decisions'][0]['status'],'NO_ENTRY')

    def test_overnight_position_rejected_without_swap_guess(self):
        with self.assertRaisesRegex(ValueError,'Overnight'):
            self.run_account([q(1),q(86400000)])

    def test_callback_failure_not_zero_pnl(self):
        with self.assertRaises(ValueError):self.run_account([q(1)],pnl_quote=lambda *args:None)
        with self.assertRaises(ValueError):self.run_account([q(1)],round_trip_cost_per_lot_usd=None)

    def test_future_outcome_input_not_accepted(self):
        c=plan();c['net_r']=2
        with self.assertRaises(ValueError):self.run_account([q(1)],[c])
        c=plan();c['eligible_after_msc']=c['known_at_msc']
        with self.assertRaises(ValueError):self.run_account([q(1)],[c])

    def test_sell_and_entry_spread_accounted(self):
        r=self.run_account([q(1),q(1000,97.9,98)],
            [plan(side='SELL',stop=101,target=98)])
        self.assertGreater(r['trades'][0]['net_usd'],0)
        self.assertLess(r['account_events'][0]['equity_usd'],3000)

    def test_no_quotes_and_budget_exhaustion_not_success(self):
        with self.assertRaises(ValueError):self.run_account([])
        with self.assertRaises(ValueError):self.run_account([q(1),q(1000)],max_quotes=1)


if __name__=='__main__':unittest.main()
