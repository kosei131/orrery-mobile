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
class CashGateTests(unittest.TestCase):
 args=GateTests.args
 def test_deposit_does_not_hide_daily_limit(self):
  r=self.args(current_equity=10400,external_cash_net=500,cash_flows_verified=True)
  self.assertEqual(r["cash_adjusted_equity"],9900)
  self.assertEqual(r["daily_drawdown"],100)
  self.assertIn("DAILY_DRAWDOWN_STOP",r["reasons"])
 def test_withdrawal_is_not_a_trading_loss(self):
  r=self.args(current_equity=9500,external_cash_net=-500,cash_flows_verified=True)
  self.assertEqual(r["daily_drawdown"],0)
  self.assertNotIn("DAILY_DRAWDOWN_STOP",r["reasons"])
  self.assertEqual(r["projected_equity_at_stops"],9450)
 def test_withdrawal_does_not_remove_actual_loss(self):
  r=self.args(current_equity=9400,external_cash_net=-500,cash_flows_verified=True)
  self.assertIn("DAILY_DRAWDOWN_STOP",r["reasons"])
 def test_deposit_never_expands_budgets(self):
  r=self.args(current_equity=20000,external_cash_net=10000,cash_flows_verified=True,
              existing_stop_risk=0,proposed_stop_risk=101)
  self.assertEqual(r["daily_loss_budget"],100)
  self.assertEqual(r["basket_risk_budget"],100)
  self.assertIn("BASKET_RISK_CAP",r["reasons"])
 def test_remaining_budget_uses_adjusted_equity(self):
  r=self.args(current_equity=10420,external_cash_net=500,cash_flows_verified=True)
  self.assertEqual(r["remaining_daily_risk"],20)
  self.assertIn("DAILY_REMAINING_RISK",r["reasons"])
 def test_existing_exposure_alone_can_exceed_remaining_daily_budget(self):
  r=self.args(current_equity=9920,existing_stop_risk=30,proposed_stop_risk=0)
  self.assertIn("DAILY_REMAINING_RISK",r["reasons"])
 def test_cash_requires_finite_value_and_true_verification(self):
  for kw in (dict(external_cash_net=500),dict(external_cash_net=-500),
             dict(external_cash_net=float("nan"),cash_flows_verified=True),
             dict(external_cash_net=1,cash_flows_verified=1)):
   with self.assertRaises(ValueError):self.args(**kw)
 def test_decimal_boundary_at_limit(self):
  r=self.args(current_equity=9900.1,external_cash_net=.1,cash_flows_verified=True)
  self.assertEqual(r["daily_drawdown"],100)
  self.assertIn("DAILY_DRAWDOWN_STOP",r["reasons"])
 def test_projected_equity_uses_real_funds_after_withdrawal(self):
  r=self.args(current_equity=40,external_cash_net=-9960,cash_flows_verified=True)
  self.assertEqual(r["cash_adjusted_equity"],10000)
  self.assertEqual(r["projected_equity_at_stops"],-10)
  self.assertIn("PROJECTED_NONPOSITIVE_EQUITY",r["reasons"])
 def test_negative_adjusted_equity_is_a_stop_not_missing_data(self):
  r=self.args(current_equity=100,external_cash_net=10100,cash_flows_verified=True)
  self.assertEqual(r["cash_adjusted_equity"],-10000)
  self.assertIn("DAILY_DRAWDOWN_STOP",r["reasons"])
  self.assertFalse(r["execution_allowed"])
if __name__=="__main__":unittest.main()
