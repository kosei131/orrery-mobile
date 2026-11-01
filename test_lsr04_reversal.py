import unittest
from lsr04_reversal import review
class ReversalTests(unittest.TestCase):
 def base(self,**kw):
  x=dict(side="BUY",htf_direction="UP",structure_confirmed=True,
         signal="BUY",signal_time=900,last_closed_time=900,now_time=900,
         line_side="UP",oscillator_direction="UP",
         indicator_verified=True,spread_verified=True,risk_verified=True)
  x.update(kw)
  return review(**x)
 def test_never_ready(self):
  self.assertEqual(self.base()["decision"],"REVIEW")
  self.assertFalse(self.base()["execution_allowed"])
 def test_future_refused(self):
  self.assertEqual(self.base(signal_time=1200)["reason"],"UNCONFIRMED_OR_FUTURE_SIGNAL")
 def test_stale_refused(self):
  self.assertEqual(self.base(now_time=2100)["reason"],"STALE_SIGNAL")
 def test_countertrend_separated(self):
  self.assertEqual(self.base(htf_direction="DOWN")["reason"],"COUNTERTREND_SEPARATE_RESEARCH_REQUIRED")
 def test_unverified_refused(self):
  self.assertEqual(self.base(indicator_verified=False)["reason"],"INDICATOR_SOURCE_OR_REPAINT_UNVERIFIED")
 def test_structure_first(self):
  self.assertEqual(self.base(structure_confirmed=False)["reason"],"PRICE_STRUCTURE_NOT_CONFIRMED")
if __name__=="__main__":unittest.main()
