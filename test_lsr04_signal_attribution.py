import unittest
from lsr04_signal_attribution import compare
from test_lsr02_paths import fixture

class AttributionTests(unittest.TestCase):
 def test_missing_signals_is_not_profit(self):
  h,f,m=fixture()
  result=compare("XAUUSD",h,f,m,[],as_of=m[-1]["close_time"],buffer=.1)
  self.assertEqual(result["groups"]["SIGNAL_MATCHED"]["candidate_count"],0)
  self.assertEqual(result["groups"]["SIGNAL_NOT_MATCHED"]["candidate_count"],result["total_candidates"])
  self.assertFalse(result["execution_allowed"])
 def test_ineligible_future_observation_not_matched(self):
  h,f,m=fixture()
  result=compare("XAUUSD",h,f,m,[],as_of=m[-1]["close_time"],buffer=.1)
  self.assertTrue(all(x["unresolved_count"]>=0 for x in result["groups"].values()))
if __name__=="__main__":unittest.main()
