import unittest
from types import SimpleNamespace
import test_demo_order_draft as fixture
from lsr04_mt5_order_draft import read_draft

class Broker:
    ACCOUNT_TRADE_MODE_DEMO=0;ORDER_TYPE_BUY=0;ORDER_TYPE_SELL=1
    def __init__(self):self.mode=0;self.changed=False;self.quote_time=10000;self.last=None
    def account_info(self):return SimpleNamespace(login=1,server='PRIVATE',trade_mode=self.mode,currency='USD',equity=10000.)
    def symbol_info(self,s):return SimpleNamespace(name=s,point=.01,trade_contract_size=100.,digits=2,
        volume_min=.01,volume_max=10.,volume_step=.01,currency_profit='USD',trade_calc_mode=4)
    def symbol_info_tick(self,s):return SimpleNamespace(bid=99.9,ask=100. if not self.changed else 100.1,time_msc=self.quote_time)
    def order_calc_profit(self,*args):self.last=args;return -100.

class ReadDraftTests(unittest.TestCase):
    def setUp(self):
        f=fixture.DraftTests();f.setUp();self.args=dict(symbol='XAUUSD',side='BUY',sweep_extreme=99.,buffer=.1,
            target=103.,lots=.25,guards=f.guards,now_msc=10001)
    def test_uses_exact_entry_and_structural_stop_in_broker_calculation(self):
        b=Broker();r=read_draft(b,**self.args)
        self.assertEqual(b.last,(0,'XAUUSD',1.,100.,98.9));self.assertFalse(r['execution_allowed'])
        self.assertNotIn('PRIVATE',str(r));self.assertEqual(r['draft']['snapshot']['broker_loss_one_lot'],100.)
    def test_real_account_and_stale_quote_block(self):
        for mode,at in [(2,10000),(0,1)]:
            b=Broker();b.mode=mode;b.quote_time=at
            with self.assertRaises(ValueError):read_draft(b,**self.args)
    def test_quote_change_during_calculation_blocks(self):
        class Changed(Broker):
            def order_calc_profit(self,*args):self.changed=True;return -100.
        with self.assertRaises(ValueError):read_draft(Changed(),**self.args)
    def test_equity_mismatch_and_missing_loss_block(self):
        with self.assertRaises(ValueError):read_draft(Broker(),**dict(self.args,guards=dict(self.args['guards'],equity=9000.)))
        class Missing(Broker):
            def order_calc_profit(self,*args):return None
        with self.assertRaises(ValueError):read_draft(Missing(),**self.args)
    def test_nonce_can_be_retained_without_plain_account_identity(self):
        a=read_draft(Broker(),**self.args);b=read_draft(Broker(),**self.args,account_nonce=a['account_nonce'])
        self.assertEqual(a['draft']['snapshot']['account_token'],b['draft']['snapshot']['account_token'])
