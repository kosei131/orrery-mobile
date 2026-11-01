import unittest
from lsr03_unique_candidates import unique_report
from test_lsr02_paths import fixture

class UniqueTests(unittest.TestCase):
 def test_unique_lifecycle_counts(self):
  for sell in (False,True):
   h,f,m=fixture(sell)
   out=unique_report("XAUUSD",h,f,m,as_of=m[-1]["close_time"],buffer=.1)
   self.assertEqual(out["structurally_confirmed"],out["vhf_confirmed"]+out["filtered"])
   self.assertEqual(len(set(c["id"] for c in out["candidates"])),out["total_candidates"])
   self.assertFalse(out["execution_allowed"])
 def test_can_count_multiple_snapshots_once(self):
  h,f,m=fixture()
  r=unique_report("XAUUSD",h,f,m,as_of=m[-1]["close_time"],buffer=.1)
  self.assertLessEqual(r["structurally_confirmed"],r["total_candidates"])
if __name__=="__main__":unittest.main()
