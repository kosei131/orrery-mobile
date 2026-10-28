import unittest
from datetime import datetime, timezone
from types import SimpleNamespace as D
from lsr04_mt5_position_risk import demo_position_risk
from lsr04_mt5_account_sync import demo_day_check
import test_lsr04_mt5_account_sync as history_fixtures

NOW = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)


def position(pid=1, side=0, symbol='XAUUSD', entry=100, sl=95, volume=1):
    return D(identifier=pid, ticket=pid+100, type=side, symbol=symbol,
             price_open=entry, sl=sl, volume=volume)


class Broker:
    ACCOUNT_TRADE_MODE_DEMO=0
    POSITION_TYPE_BUY=0
    POSITION_TYPE_SELL=1
    ORDER_TYPE_BUY=0
    ORDER_TYPE_SELL=1
    DEAL_TYPE_BUY=0
    DEAL_TYPE_SELL=1
    DEAL_ENTRY_IN=0
    DEAL_ENTRY_OUT=1
    DEAL_ENTRY_INOUT=2

    def __init__(self, positions=None):
        self.positions=[position()] if positions is None else positions
        self.account=D(login=1, server='demo', currency='USD', trade_mode=0, equity=10000, balance=10000)
        self.tick=D(bid=110, ask=111, time_msc=int(NOW.timestamp()*1000))
        self.calls=[]

    def account_info(self):return self.account
    def positions_get(self):return self.positions
    def symbol_info(self, symbol):return D(name=symbol)
    def symbol_info_tick(self, symbol):return self.tick
    def order_calc_profit(self, action, symbol, volume, start, end):
        self.calls.append((action, symbol, volume, start, end))
        return (end-start)*volume*(1 if action==0 else -1)
    def history_deals_get(self, a, b):return []


class Valuation(unittest.TestCase):
    def run_risk(self, broker=None, **kw):
        args=dict(now_utc=NOW, cost_allowances={1:2})
        args.update(kw)
        return demo_position_risk(broker or Broker(), **args)

    def assert_blocked(self, r):
        self.assertEqual(r['status'], 'BLOCKED_POSITION_RISK')
        self.assertIsNone(r['total_incremental_stop_risk'])
        self.assertEqual(r['positions'], [])
        self.assertFalse(r['execution_allowed'])

    def test_current_equity_risk_not_entry_loss(self):
        b=Broker();r=self.run_risk(b)
        self.assertEqual(r['positions'][0]['entry_to_stop_pnl'], -5)
        self.assertEqual(r['total_incremental_stop_risk'], 17)
        self.assertIn((0,'XAUUSD',1,110,95), b.calls)
        self.assertFalse(r['execution_allowed'])

    def test_locked_profit_still_has_equity_risk(self):
        r=self.run_risk(Broker([position(sl=105)]))
        self.assertEqual(r['positions'][0]['entry_to_stop_pnl'], 5)
        self.assertEqual(r['total_incremental_stop_risk'], 7)

    def test_sell_uses_ask_and_actual_volume(self):
        b=Broker([position(side=1, sl=120, entry=115, volume=.5)])
        r=self.run_risk(b)
        self.assertEqual(r['total_incremental_stop_risk'], 6.5)
        self.assertIn((1,'XAUUSD',.5,111,120), b.calls)

    def test_account_wide_sum_no_profit_offset(self):
        b=Broker([position(sl=105), position(2,1,'USDJPY',115,120)])
        r=self.run_risk(b,cost_allowances={1:2,2:3})
        self.assertEqual(r['total_incremental_stop_risk'], 19)
        self.assertEqual(len(r['positions']),2)

    def test_no_positions_requires_explicit_empty_costs(self):
        r=self.run_risk(Broker([]),cost_allowances={})
        self.assertEqual(r['total_incremental_stop_risk'],0)

    def test_missing_sl_or_unknown_side_blocks(self):
        for p in (position(sl=0),position(side=9),position(volume=0),position(entry=float('nan'))):
            self.assert_blocked(self.run_risk(Broker([p])))

    def test_missing_or_extra_allowances_block(self):
        for allowances in ({},{1:0,99:0}):
            self.assert_blocked(self.run_risk(cost_allowances=allowances))
        with self.assertRaises(ValueError):self.run_risk(cost_allowances={1:-1})

    def test_unknown_symbol_blocks(self):
        b=Broker();b.symbol_info=lambda symbol:None
        self.assert_blocked(self.run_risk(b))

    def test_stale_future_or_crossed_quote_blocks(self):
        for delta in (-6000,1):
            b=Broker();b.tick.time_msc+=delta
            self.assert_blocked(self.run_risk(b))
        b=Broker();b.tick.ask=109
        self.assert_blocked(self.run_risk(b))

    def test_already_crossed_stop_blocks(self):
        for p in (position(sl=110),position(side=1,sl=110)):
            self.assert_blocked(self.run_risk(Broker([p])))

    def test_failed_or_positive_broker_increment_blocks(self):
        for value in (None,float('nan'),10):
            b=Broker();b.order_calc_profit=lambda *a:value
            self.assert_blocked(self.run_risk(b))

    def test_account_switch_and_live_mode_block(self):
        b=Broker();b.account.trade_mode=2
        self.assert_blocked(self.run_risk(b))
        class Switch(Broker):
            count=0
            def account_info(self):
                self.count+=1
                return D(**dict(vars(self.account),login=self.count))
        self.assert_blocked(self.run_risk(Switch()))

    def test_position_change_during_capture_blocks(self):
        class Changed(Broker):
            count=0
            def positions_get(self):
                self.count+=1
                return [position(sl=95 if self.count==1 else 94)]
        self.assert_blocked(self.run_risk(Changed()))

    def test_equity_change_during_capture_blocks(self):
        class Changed(Broker):
            count=0
            def account_info(self):
                self.count+=1
                return D(**dict(vars(self.account),equity=10000+self.count))
        self.assert_blocked(self.run_risk(Changed()))

    def test_duplicate_position_blocks(self):
        self.assert_blocked(self.run_risk(Broker([position(),position()])))

    def test_expected_snapshot_mismatch_blocks(self):
        self.assert_blocked(self.run_risk(expected_positions=[position(sl=94)]))

    def test_cost_unknown_never_becomes_zero(self):
        with self.assertRaises(ValueError):self.run_risk(cost_allowances=None)

    def test_bridge_includes_exposure_even_with_unknown_streak(self):
        b=Broker()
        # Open histories remain uncertified; still expose the independent risk result.
        r=demo_day_check(b,**history_fixtures.Tests().kw(stop_cost_allowances={1:2}))
        self.assertEqual(r['status'],'BLOCKED_NO_AUTHORITATIVE_STREAK')
        self.assertEqual(r['stop_exposure']['total_incremental_stop_risk'],17)

    def test_bridge_valuation_failure_stops_before_gate(self):
        b=Broker([position(sl=0)])
        r=demo_day_check(b,**history_fixtures.Tests().kw(stop_cost_allowances={1:2}))
        self.assertEqual(r['status'],'BLOCKED_POSITION_RISK')
        self.assertNotIn('risk_review',r)

    def test_bridge_uses_broker_total_for_empty_snapshot(self):
        # No positions gives a certified empty snapshot for this research model.
        b=Broker([])
        r=demo_day_check(b,**history_fixtures.Tests().kw(history_complete=True,
            existing_stop_risk=999,stop_cost_allowances={}))
        self.assertEqual(r['risk_review']['total_stop_risk'],20)
        self.assertEqual(r['status'],'BLOCKED_DAILY_RECONCILIATION')


if __name__=='__main__':unittest.main()
