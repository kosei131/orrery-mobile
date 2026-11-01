import unittest
from lsr02_seeded_replay import simulate,compare

class LossStopTests(unittest.TestCase):
 def test_streak_halt_and_fixed_price_series(self):
  a=simulate(seed=71,steps=1500,loss_streak_stop=2)
  b=simulate(seed=71,steps=1500)
  self.assertEqual(a["price_series_sha256"],b["price_series_sha256"])
  self.assertLessEqual(a["trades"],b["trades"])
  if a["halted_at"] is not None:
   self.assertTrue(all(t["exit_at"]<=a["halted_at"] for t in a["ledger"]))
  self.assertFalse(a["execution_allowed"])
 def test_invalid_stop(self):
  for stop in (0,-1,1.5,True):
   with self.assertRaises(ValueError):simulate(loss_streak_stop=stop)
 def test_compare_reproducible_with_stop(self):
  r=compare(seed=99,steps=450,loss_streak_stop=3)
  self.assertEqual(r["baseline"]["price_series_sha256"],r["filtered"]["price_series_sha256"])
if __name__=="__main__":unittest.main()
