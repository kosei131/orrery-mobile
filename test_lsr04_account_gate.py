import unittest
from datetime import datetime,timezone
from lsr04_account_gate import review
class GateTests(unittest.TestCase):
 def args(self,**kw):
  a=dict(day_start_utc=datetime(2026,10,27,tzinfo=timezone.utc),
         now_utc=datetime(2026,10,27,12,tzinfo=timezone.utc),
         day_start_equity=10000,current_equity=9980,
         existing_stop_risk=20,proposed_stop_risk=30,consecutive_losses=0)
  a.update(kw);return review(**a)
 def test_permitted_only_for_research(self):
  r=self.args();self.assertEqual(r["status"],"RESEARCH_WITHIN_LIMITS")
  self.assertFalse(r["execution_allowed"])
 def test_three_losses_stop(self):
  self.assertIn("LOSS_STREAK_STOP",self.args(consecutive_losses=3)["reasons"])
 def test_daily_limit(self):
  self.assertIn("DAILY_DRAWDOWN_STOP",self.args(current_equity=9900)["reasons"])
 def test_basket_limit(self):
  self.assertIn("BASKET_RISK_CAP",self.args(existing_stop_risk=90)["reasons"])
 def test_remaining_daily_risk(self):
  self.assertIn("DAILY_REMAINING_RISK",self.args(current_equity=9920)["reasons"])
 def test_session_mismatch_rejected(self):
  with self.assertRaises(ValueError):self.args(now_utc=datetime(2026,10,28,12,tzinfo=timezone.utc))
if __name__=="__main__":unittest.main()
