import unittest
from types import SimpleNamespace
import test_mt5_order_draft as fixture
from lsr04_demo_preflight import review

class Broker(fixture.Broker):
    def account_info(self):
        a=super().account_info();a.margin_free=5000.;a.trade_allowed=True;a.trade_expert=True;return a
    def terminal_info(self):return SimpleNamespace(connected=True,trade_allowed=True,tradeapi_disabled=False)
    def symbol_info(self,s):
        a=super().symbol_info(s);a.trade_mode=4;a.order_mode=49;a.trade_stops_level=10;a.trade_freeze_level=5;a.trade_tick_size=.01;return a
    def order_calc_margin(self,*args):return 100.

class PreflightTests(unittest.TestCase):
    setUp=fixture.ReadDraftTests.setUp
    def test_valid_remains_review_only(self):
        r=review(Broker(),**self.args);self.assertEqual(r['estimated_margin'],100.)
        self.assertFalse(r['execution_allowed']);self.assertFalse(r['broker_session_verified'])
    def test_minimum_distance_does_not_move_stop(self):
        class Near(Broker):
            def symbol_info(self,s):
                a=super().symbol_info(s);a.trade_stops_level=101;return a
        with self.assertRaises(ValueError):review(Near(),**self.args)
    def test_missing_or_excess_margin_refused(self):
        for value in (None,0.,6000.):
            class Bad(Broker):
                def order_calc_margin(self,*args):return value
            with self.assertRaises(ValueError):review(Bad(),**self.args)
    def test_close_only_and_no_sl_permission_refused(self):
        for mode,bits in ((3,49),(4,1),(0,49)):
            class Disabled(Broker):
                def symbol_info(self,s):
                    a=super().symbol_info(s);a.trade_mode=mode;a.order_mode=bits;return a
            with self.assertRaises(ValueError):review(Disabled(),**self.args)
    def test_terminal_disabled_refused(self):
        class Disabled(Broker):
            def terminal_info(self):return SimpleNamespace(connected=True,trade_allowed=False,tradeapi_disabled=False)
        with self.assertRaises(ValueError):review(Disabled(),**self.args)
    def test_quote_change_in_margin_calculation_refused(self):
        class Changed(Broker):
            def order_calc_margin(self,*args):self.changed=True;return 100.
        with self.assertRaises(ValueError):review(Changed(),**self.args)
    def test_equity_change_after_draft_refused(self):
        class Changed(Broker):
            def order_calc_margin(self,*args):self.new_equity=9000.;return 100.
            def account_info(self):
                a=super().account_info();a.equity=getattr(self,'new_equity',a.equity);return a
        with self.assertRaisesRegex(ValueError,'context changed'):review(Changed(),**self.args)
    def test_off_grid_stop_refused_without_rounding(self):
        args=dict(self.args,buffer=.105)
        with self.assertRaisesRegex(ValueError,'price grid'):review(Broker(),**args)
