import unittest
from lsr02_equity_audit import audit
class EquityAuditTests(unittest.TestCase):
 def args(self):return dict(contract_units=100,usd_per_quote_unit=1,risk_cap_usd=300,estimated_exit_cost_usd=7)
 def rows(self):
  p=[dict(side="BUY",entry=4500,stop=4495,lots=1)]
  return [
   dict(timestamp=1,bid=4500,ask=4500.2,balance_usd=10000,equity_usd=10000,positions=[]),
   dict(timestamp=2,bid=4498,ask=4498.2,balance_usd=10000,equity_usd=9800,positions=p),
   dict(timestamp=3,bid=4496,ask=4496.2,balance_usd=10000,equity_usd=9600,positions=p),
   dict(timestamp=4,bid=4501,ask=4501.2,balance_usd=10000,equity_usd=10100,positions=p)]
 def test_peak_dd_and_exposure(self):
  r=audit(self.rows(),**self.args())
  self.assertEqual(r["max_equity_drawdown_usd"],"400")
  self.assertEqual(r["max_open_positions"],1)
  self.assertEqual(r["max_gross_lots"],"1")
  self.assertGreaterEqual(len(r["risk_breaches"]),1)
  self.assertFalse(r["execution_allowed"])
 def test_rejects_nonchronological(self):
  rows=self.rows();rows[2]["timestamp"]=2
  with self.assertRaises(ValueError):audit(rows,**self.args())
 def test_requires_complete_account_equity(self):
  rows=self.rows();rows[1]["equity_usd"]=float("nan")
  with self.assertRaises(ValueError):audit(rows,**self.args())
if __name__=="__main__":unittest.main()
