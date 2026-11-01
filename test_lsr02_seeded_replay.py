import unittest
from lsr02_seeded_replay import simulate,compare
class ReplayTests(unittest.TestCase):
 def test_reproducible(self):
  a=simulate(seed=123,steps=300);b=simulate(seed=123,steps=300)
  self.assertEqual(a,b)
  self.assertFalse(a["execution_allowed"])
 def test_identical_market_for_variants(self):
  x=compare(seed=456,steps=450)
  self.assertEqual(x["baseline"]["price_series_sha256"],x["filtered"]["price_series_sha256"])
  self.assertLessEqual(x["filtered"]["trades"],x["baseline"]["trades"])
 def test_invalid(self):
  with self.assertRaises(ValueError):simulate(steps=10)
if __name__=="__main__":unittest.main()
