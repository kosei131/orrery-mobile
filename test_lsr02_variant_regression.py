"""Regression check of one seeded synthetic comparison, NOT an edge claim."""
import unittest
from lsr02_compare_variants import run

EXPECTED={
 "BASE":(514,234,10391.91,585.85),
 "ADX":(230,111,4555.33,303.00),
 "ATR":(227,83,1410.33,417.31),
 "ADX_ATR":(113,48,1339.58,204.48),
}
class SyntheticComparisonRegression(unittest.TestCase):
 def test_pinned_replay_metrics(self):
  rows=run()
  self.assertEqual(set(x["variant"] for x in rows),set(EXPECTED))
  self.assertEqual(len(set(x["price_hash"] for x in rows)),1)
  for x in rows:
   self.assertEqual((x["trades"],x["wins"],x["net_pnl_usd"],x["sampled_max_drawdown_usd"]),EXPECTED[x["variant"]])
if __name__=="__main__":unittest.main()
