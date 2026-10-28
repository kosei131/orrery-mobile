import unittest
from lsr03_candidate_report import report
from test_lsr02_paths import fixture
class CandidateReportTests(unittest.TestCase):
 def test_counts_match(self):
  for sell in (False,True):
   h,f,m=fixture(sell)
   r=report("XAUUSD",h,f,m,as_of=m[-1]["close_time"],buffer=.1)
   self.assertEqual(r["base_reviewable"],r["vhf_reviewable"]+r["vhf_filtered_rows"])
   self.assertLessEqual(r["vhf_reviewable"],r["base_reviewable"])
   self.assertFalse(r["execution_allowed"])
if __name__=="__main__":unittest.main()
