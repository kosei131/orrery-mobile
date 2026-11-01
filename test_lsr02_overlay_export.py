import unittest
from lsr02_overlay_export import overlay
class OverlayTests(unittest.TestCase):
 def bars(self,n=100):
  return [dict(open=100,high=101,low=99,close=100,close_time=(i+1)*300) for i in range(n)]
 def args(self):
  return dict(symbol="XAUUSD",interval=300,as_of=30000,tenkan=9,kijun=26,span_b=52,shift=26,source="SYNTHETIC_TEST",source_verified=False)
 def test_observations_exported_without_orders(self):
  r=overlay(self.bars(),**self.args())
  self.assertEqual(r["schema"],"ORRERY_OVERLAY_V1")
  self.assertEqual(r["cloud_location"],"INSIDE")
  self.assertEqual(r["status"],"WAIT")
  self.assertFalse(r["execution_allowed"])
 def test_gap_and_stale_fail(self):
  b=self.bars(); del b[25]
  with self.assertRaises(ValueError): overlay(b,**self.args())
  a=self.args();a["as_of"]=30600
  with self.assertRaises(ValueError):overlay(self.bars(),**a)
 def test_unverified_demo_refused(self):
  a=self.args();a["source"]="VERIFIED_DEMO_CLOSED_BARS"
  with self.assertRaises(ValueError):overlay(self.bars(),**a)
if __name__=="__main__":unittest.main()
