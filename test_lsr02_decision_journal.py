import unittest
from lsr02_decision_journal import decide
class DecisionTests(unittest.TestCase):
    def args(self):
        return dict(market_regime="TREND",data_fresh=True,spread_ok=True,
          news_clear=True,risk_budget_ok=True,loss_halt=False,timestamp=100,
          candidates=[dict(mode="STRUCTURE",direction="BUY",entry=100,stop=99,
               target=103,expected_net_rr=2.0,invalidation=99,note="2.6 level retest",
               signal_confirmed=False)])
    def test_wait_is_an_explicit_reason(self):
        a=self.args();r=decide(**a)
        self.assertEqual(r["status"],"WAIT")
        self.assertEqual(r["candidates"][0]["reason"],"CONFIRMATION_PENDING")
        self.assertFalse(r["execution_allowed"])
    def test_eligible_still_requires_human(self):
        a=self.args();a["candidates"][0]["signal_confirmed"]=True
        r=decide(**a);self.assertEqual(r["status"],"REVIEW")
        self.assertTrue(r["human_approval_required"])
        self.assertFalse(r["execution_allowed"])
    def test_defense_before_trade(self):
        for k,v,expected in (("data_fresh",False,"STALE_DATA"),
            ("loss_halt",True,"LOSS_HALT"),("risk_budget_ok",False,"RISK_BUDGET_EXCEEDED")):
            a=self.args();a[k]=v;r=decide(**a)
            self.assertEqual(r["status"],"DEFENSE");self.assertEqual(r["reason_codes"],[expected])
    def test_regime_mismatch(self):
        a=self.args();a["market_regime"]="RANGE";a["candidates"][0]["signal_confirmed"]=True
        r=decide(**a);self.assertEqual(r["status"],"WAIT")
        self.assertEqual(r["candidates"][0]["reason"],"REGIME_MISMATCH")
    def test_bad_data(self):
        a=self.args();a["candidates"][0]["expected_net_rr"]=float("nan")
        with self.assertRaises(ValueError):decide(**a)
if __name__=="__main__":unittest.main()
