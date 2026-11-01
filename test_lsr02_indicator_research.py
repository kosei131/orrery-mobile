import unittest
from lsr02_indicator_research import metrics,filter_trend
class IndicatorTests(unittest.TestCase):
 def bars(self,n=60):
  return [dict(high=100+i*.3+1,low=100+i*.3-1,close=100+i*.3) for i in range(n)]
 def test_trending(self):
  r=filter_trend(self.bars())
  self.assertEqual(r["status"],"OK")
  self.assertEqual(r["decision"],"UP_TREND_CANDIDATE")
  self.assertFalse(r["execution_allowed"])
 def test_short_history(self):
  self.assertEqual(filter_trend(self.bars(20))["decision"],"WAIT_HISTORY")
 def test_no_future_leak(self):
  a=metrics(self.bars(40))
  b=metrics(self.bars(40)+[dict(high=10000,low=1,close=9999)])
  self.assertNotEqual(a["atr"],b["atr"])
 def test_invalid(self):
  b=self.bars();b[4]["close"]=999999
  with self.assertRaises(ValueError):metrics(b)
if __name__=="__main__":unittest.main()
