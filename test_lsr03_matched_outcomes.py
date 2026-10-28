import unittest
from lsr03_matched_outcomes import audit
from test_lsr02_paths import fixture
class MatchedOutcomeTests(unittest.TestCase):
 def test_same_outcome_for_groups(self):
  for sell in (False,True):
   h,f,m=fixture(sell)
   out=audit("XAUUSD",h,f,m,as_of=m[-1]["close_time"],buffer=.1)
   self.assertFalse(out["execution_allowed"])
   self.assertEqual(sum(v["candidates"] for v in out["groups"].values()),len(out["rows"]))
   self.assertEqual(len({x["id"] for x in out["rows"]}),len(out["rows"]))
   for row in out["rows"]:
    if row["status"] in ("OPEN","CLOSED"):
     self.assertGreater(row["entry_at"],row["structural_at"])
 def test_no_future_fill(self):
  h,f,m=fixture()
  m=m[:12]
  result=audit("XAUUSD",h,f,m,as_of=m[-1]["close_time"],buffer=.1)
  self.assertFalse(result["execution_allowed"])
if __name__=="__main__":unittest.main()
