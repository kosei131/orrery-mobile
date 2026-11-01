import unittest
from lsr02_seeded_replay import simulate
class HoldingTests(unittest.TestCase):
 def test_held_positions_do_not_overlap(self):
  r=simulate(seed=260427,steps=1500,use_atr_stop=True)
  closed=r["ledger"]
  self.assertTrue(all(closed[i]["entry_at"]>closed[i-1]["exit_at"] for i in range(1,len(closed))))
  self.assertTrue(any(t["exit_at"]>t["entry_at"] for t in closed))
  self.assertEqual(len(r["equity_curve"]),1499)
  self.assertFalse(r["execution_allowed"])
 def test_unclosed_is_not_counted_as_win(self):
  r=simulate(seed=5,steps=100,use_atr_stop=True)
  self.assertEqual(r["trades"],len(r["ledger"]))
  if r["unclosed"] is not None:
   self.assertNotIn("net_pnl_usd",r["unclosed"])
if __name__=="__main__":unittest.main()
