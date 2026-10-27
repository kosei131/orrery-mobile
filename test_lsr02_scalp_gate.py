import unittest
from lsr02_scalp_gate import evaluate
class ScalpTests(unittest.TestCase):
    def args(self):
        return dict(side="BUY",entry=4500,stop=4499,target=4502,lots=1,
            contract_units=100,usd_per_quote_unit=1,spread_price=".15",
            slippage_price=".10",commission_usd_per_lot_roundtrip=7,
            equity_usd=100000,max_risk_fraction=".0025",max_open_risk_usd=250,
            existing_open_risk_usd=0,max_hold_seconds=30,quote_age_seconds=1,
            is_demo=True,spec_verified=True)
    def test_one_lot(self):
        r=evaluate(**self.args());self.assertEqual(r["status"],"RESEARCH_CANDIDATE")
        self.assertEqual(r["net_target_usd"],"168.00")
        self.assertEqual(r["estimated_stop_loss_usd"],"132.00")
        self.assertFalse(r["execution_allowed"])
    def test_two_lots_rejected_on_budget(self):
        a=self.args();a["lots"]=2
        self.assertEqual(evaluate(**a)["status"],"SKIP")
    def test_stale_or_unverified(self):
        for k,v in (("quote_age_seconds",4),("spec_verified",False),
                    ("max_hold_seconds",181)):
            a=self.args();a[k]=v;self.assertEqual(evaluate(**a)["status"],"SKIP")
    def test_live_and_approval_disallowed(self):
        for k,v in (("is_demo",False),("human_approved",True)):
            a=self.args();a[k]=v
            with self.assertRaises(ValueError):evaluate(**a)
    def test_cost_eats_edge(self):
        a=self.args();a["spread_price"]=2
        self.assertEqual(evaluate(**a)["status"],"SKIP")
if __name__=="__main__":unittest.main()
