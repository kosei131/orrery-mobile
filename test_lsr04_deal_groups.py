import unittest
from types import SimpleNamespace as D
from lsr04_deal_groups import reconcile
def deal(pid,ticket,entry,vol,pnl=0,fee=0):
 return D(position_id=pid,time_msc=ticket*1000,ticket=ticket,entry=entry,volume=vol,
          profit=pnl,commission=0,swap=0,fee=fee)
class Groups(unittest.TestCase):
 def test_two_partial_exits_one_loss(self):
  a=[deal(10,1,0,1),deal(10,2,1,.4,-4,fee=-1),deal(10,3,1,.6,-6)]
  r=reconcile(a,entry_in=0,entry_out=1,entry_inout=2)
  self.assertEqual(r["completed_positions"],1)
  self.assertEqual(r["consecutive_losses"],1)
  self.assertEqual(r["positions"][0]["net"],-11)
 def test_open_blocks_streak(self):
  r=reconcile([deal(10,1,0,1)],entry_in=0,entry_out=1,entry_inout=2)
  self.assertIsNone(r["consecutive_losses"])
 def test_mixed_reversal_blocks(self):
  r=reconcile([deal(10,1,0,1),deal(10,2,2,2)],entry_in=0,entry_out=1,entry_inout=2)
  self.assertIsNone(r["consecutive_losses"])
 def test_unknown_fee_blocks(self):
  x=deal(10,1,0,1);del x.fee
  with self.assertRaises(ValueError):reconcile([x],entry_in=0,entry_out=1,entry_inout=2)
if __name__=="__main__":unittest.main()
