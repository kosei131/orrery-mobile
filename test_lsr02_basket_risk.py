import unittest
from lsr02_basket_risk import evaluate
class BasketTests(unittest.TestCase):
 def args(self):
  return dict(bid=4498,ask=4498.2,contract_units=100,usd_per_quote_unit=1,
              equity_usd=9800,balance_usd=10000,risk_cap_usd=400,
              estimated_exit_cost_usd=7)
 def test_two_longs_unrealized_and_stop(self):
  p=[dict(side="BUY",entry=4500,lots=1,stop=4495),
     dict(side="BUY",entry=4499,lots=1,stop=4495)]
  r=evaluate(p,**self.args())
  self.assertEqual(r["unrealized_pnl_usd"],"-300")
  self.assertEqual(r["aggregate_stop_pnl_from_entries_usd"],"-914")
  self.assertEqual(r["incremental_loss_to_stops_usd"],"614")
  self.assertFalse(r["risk_cap_ok"])
  self.assertFalse(r["execution_allowed"])
 def test_short_marks_ask_not_bid(self):
  p=[dict(side="SELL",entry=4500,lots=1,stop=4505)]
  r=evaluate(p,**self.args())
  self.assertEqual(r["unrealized_pnl_usd"],"180.0")
 def test_mixed_and_missing_stop_rejected(self):
  with self.assertRaises(ValueError):
   evaluate([dict(side="BUY",entry=4500,lots=1,stop=4505)],**self.args())
  with self.assertRaises(ValueError):
   evaluate([dict(side="BUY",entry=4500,lots=1)],**self.args())
if __name__=="__main__":unittest.main()
