import unittest
from lsr04_signal_journal import SignalJournal
class JournalTests(unittest.TestCase):
 def test_revision_flagged_not_erased(self):
  j=SignalJournal()
  x=dict(symbol="XAUUSD",timeframe="M5",closed_at=300,source="unknown-video",
         revision_id="unverified")
  self.assertFalse(j.observe(**x,observed_at=310,signal="BUY")["changed_after_observation"])
  self.assertTrue(j.observe(**x,observed_at=610,signal="NONE")["changed_after_observation"])
  r=j.report();self.assertEqual(r["repaint_suspicions"],1)
  self.assertEqual(r["events"][0]["signal"],"BUY")
  self.assertFalse(r["execution_allowed"])
 def test_reject_future_and_retroactive_observation(self):
  j=SignalJournal()
  x=dict(symbol="USDJPY",timeframe="M5",closed_at=300,source="s",revision_id="v")
  with self.assertRaises(ValueError):j.observe(**x,observed_at=200,signal="BUY")
  j.observe(**x,observed_at=320,signal="BUY")
  with self.assertRaises(ValueError):j.observe(**x,observed_at=310,signal="SELL")
 def test_version_isolation(self):
  j=SignalJournal()
  base=dict(symbol="XAUUSD",timeframe="M5",closed_at=300,observed_at=310,source="s")
  j.observe(**base,revision_id="v1",signal="BUY")
  self.assertFalse(j.observe(**base,revision_id="v2",signal="SELL")["changed_after_observation"])
if __name__=="__main__":unittest.main()
