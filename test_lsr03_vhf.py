import unittest
from lsr03_vhf import calculate,confirm_structure

class VHFTests(unittest.TestCase):
 def bars(self,prices):
  return [dict(close=p,close_time=(i+1)*300) for i,p in enumerate(prices)]
 def test_straight_trend_is_strength_not_direction(self):
  r=calculate(self.bars([100+i for i in range(35)]),period=14,as_of=10500,interval=300)
  self.assertEqual(r["status"],"OK")
  self.assertGreater(r["value"],.8)
  self.assertEqual(r["direction"],"UNDEFINED")
  self.assertFalse(r["execution_allowed"])
 def test_flat_window_is_zero(self):
  r=calculate(self.bars([100]*35),period=14)
  self.assertEqual(r["value"],0)
 def test_wick_and_no_break_cannot_confirm(self):
  bars=self.bars([100+i for i in range(34)]+[134])
  r=confirm_structure(bars,breakout_side="BUY",breakout_level=110,period=14)
  self.assertEqual(r["decision"],"WAIT")
 def test_reject_future_and_gaps(self):
  b=self.bars([100+i for i in range(35)])
  with self.assertRaises(ValueError):calculate(b,period=14,as_of=6000,interval=300)
  b[2]["close_time"]+=1
  with self.assertRaises(ValueError):calculate(b,period=14,as_of=10500,interval=300)
 def test_no_history(self):
  self.assertEqual(calculate(self.bars([1,2,3]),period=14)["status"],"INSUFFICIENT_HISTORY")
if __name__=="__main__": unittest.main()
