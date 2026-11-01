import unittest
from lsr02_level_observer import observe
class ObserverTests(unittest.TestCase):
 def bars(self,n):
  return [dict(open=100,close=100,high=101,low=99,close_time=(i+1)*300) for i in range(n)]
 def run_observe(self,bars):
  return observe(bars,as_of=bars[-1]["close_time"],interval=300,
          tenkan=9,kijun=26,span_b=52,shift=26)
 def test_history_boundary_never_orders(self):
  old=self.run_observe(self.bars(70))
  self.assertIn("CLOUD_HISTORY_NOT_AVAILABLE",old["reasons"])
  full=self.run_observe(self.bars(100))
  self.assertEqual(full["cloud_location"],"INSIDE")
  self.assertFalse(full["execution_allowed"])
  self.assertEqual(full["status"],"WAIT")
 def test_missing_bar_fails_closed(self):
  bars=self.bars(100);del bars[20]
  with self.assertRaises(ValueError):self.run_observe(bars)
if __name__=="__main__":unittest.main()
