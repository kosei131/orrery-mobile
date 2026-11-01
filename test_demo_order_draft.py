import unittest
from copy import deepcopy
import test_lsr02_risk_plan as fixture
from lsr04_demo_order_draft import prepare,recheck

class DraftTests(unittest.TestCase):
    def setUp(self):
        a=fixture.RiskPlanTests().args()
        self.guards={k:v for k,v in a.items() if k not in ('side','entry','sweep_extreme','buffer','target')}
        self.s=dict(account_token='LOCAL_TEST',mode='DEMO',symbol='XAUUSD',bid=99.9,ask=100.,
            quote_msc=10000,volume_min=.01,volume_max=10.,volume_step=.01,
            broker_loss_one_lot=100.,spec_token='SYNTHETIC_SPEC')
        self.args=dict(snapshot=self.s,side='BUY',sweep_extreme=99.,buffer=.1,target=103.,
                       lots=.25,guards=self.guards,now_msc=10001)
    def test_draft_and_recheck_never_enable_orders(self):
        d=prepare(**self.args);r=recheck(d,current_snapshot=self.s,current_guards=self.guards,now_msc=11000)
        self.assertEqual(d['stop'],98.9);self.assertFalse(r['execution_allowed'])
    def test_real_mode_and_stale_quote_rejected(self):
        with self.assertRaises(ValueError):prepare(**dict(self.args,snapshot=dict(self.s,mode='REAL')))
        with self.assertRaises(ValueError):prepare(**dict(self.args,now_msc=15001))
    def test_quote_account_and_spec_changes_invalidate(self):
        d=prepare(**self.args)
        for k,v in [('ask',100.1),('account_token','OTHER'),('spec_token','CHANGED')]:
            with self.assertRaises(ValueError):recheck(d,current_snapshot=dict(self.s,**{k:v}),current_guards=self.guards,now_msc=11000)
    def test_tamper_and_risk_change_rejected(self):
        d=prepare(**self.args);bad=deepcopy(d);bad['lots']=2
        with self.assertRaises(ValueError):recheck(bad,current_snapshot=self.s,current_guards=self.guards,now_msc=11000)
        with self.assertRaises(ValueError):recheck(d,current_snapshot=self.s,current_guards=dict(self.guards,consecutive_losses=3),now_msc=11000)
    def test_three_losses_and_bad_lots_block(self):
        with self.assertRaises(ValueError):prepare(**dict(self.args,guards=dict(self.guards,consecutive_losses=3)))
        for lots in (.251,.26):
            with self.assertRaises(ValueError):prepare(**dict(self.args,lots=lots))
