import unittest
from lsr04_broker_sizing import size_from_broker_quote as size
class SizeTests(unittest.TestCase):
 def data(self,**changes):
  x=dict(account_currency="USD",equity=10000,risk_fraction=.005,
    broker_loss_one_lot=-200,volume_min=.01,volume_max=10,volume_step=.01)
  x.update(changes)
  return size(**x)
 def test_lots_under_budget(self):
  r=self.data()
  self.assertEqual(r["lots"],.25)
  self.assertEqual(r["modeled_stop_loss"],-50)
  self.assertFalse(r["execution_allowed"])
 def test_existing_portfolio_exposure(self):
  self.assertEqual(self.data(max_portfolio_risk_currency=40)["lots"],.05)
 def test_below_minimum(self):
  self.assertEqual(self.data(broker_loss_one_lot=-10000)["status"],"BELOW_MIN_LOT")
 def test_reject_unverified_values(self):
  with self.assertRaises(ValueError):self.data(broker_loss_one_lot=200)
if __name__=="__main__":unittest.main()
