import unittest
from lsr04_asof_join import align
from test_lsr02_paths import fixture

class AsOfTests(unittest.TestCase):
 def test_future_observation_does_not_match(self):
  h,f,m=fixture()
  t=m[-1]["close_time"]
  base=align("XAUUSD",h,f,m,[],as_of=t,buffer=.1)
  self.assertFalse(base["execution_allowed"])
  self.assertTrue(all(x["reversal_signal"]=="WAIT_NO_MATCH" for x in base["rows"]))
  if base["rows"]:
   first=base["rows"][0]
   e=dict(symbol="XAUUSD",timeframe="M5",signal=first["side"],
          closed_at=first["structural_at"],observed_at=first["structural_at"]+300,
          source="test",revision_id="v1")
   out=align("XAUUSD",h,f,m,[e],as_of=t,buffer=.1)
   self.assertEqual(out["rows"][0]["reversal_signal"],"WAIT_NO_MATCH")
 def test_reject_invalid(self):
  h,f,m=fixture()
  with self.assertRaises(ValueError):
   align("XAUUSD",h,f,m,[dict(symbol="XAUUSD",timeframe="M5",signal="BUY",closed_at=300,observed_at=999999)],as_of=m[-1]["close_time"],buffer=.1)
if __name__=="__main__":unittest.main()
