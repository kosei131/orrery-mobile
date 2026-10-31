import unittest
from lsr03_adapter import compare_vhf
from test_lsr02_paths import fixture

class AdapterTests(unittest.TestCase):
 def run_comparison(self,h,f,m):
  return compare_vhf("XAUUSD",h,f,m,as_of=m[-1]["close_time"],
                     buffer=.1,period=2)
 def test_no_future_and_no_ready(self):
  h,f,m=fixture()
  result=self.run_comparison(h,f,m)
  self.assertTrue(result["base_trace"])
  self.assertTrue(all(x["decision"] in ("WAIT","REVIEW","CANCEL") for x in result["vhf_trace"]))
  self.assertTrue(all(not x["execution_allowed"] for x in result["vhf_trace"]))
  # Modifying a future 15m bar cannot change earlier VHF annotations.
  cutoff=result["base_trace"][0]["at"]
  f2=[dict(x) for x in f]
  f2[-1]["close"]+=.01
  earlier=self.run_comparison(h,f2,m)
  self.assertEqual(
   [x for x in result["vhf_trace"] if x["at"]<f[-1]["close_time"]],
   [x for x in earlier["vhf_trace"] if x["at"]<f[-1]["close_time"]])
 def test_no_unsupported_ready(self):
  h,f,m=fixture(True)
  out=self.run_comparison(h,f,m)
  self.assertFalse(out["execution_allowed"])
if __name__=="__main__":unittest.main()
