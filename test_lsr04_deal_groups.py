import unittest
from types import SimpleNamespace as D
from lsr04_deal_groups import reconcile
def deal(pid,ticket,entry,vol,pnl=0,fee=0):
 return D(position_id=pid,time_msc=ticket*1000,ticket=ticket,entry=entry,volume=vol,
          profit=pnl,commission=0,swap=0,fee=fee)
class Groups(unittest.TestCase):
 def test_two_partial_exits_one_loss(self):
  a=[deal(10,1,0,1),deal(10,2,1,.4,-4,fee=-1),deal(10,3,1,.6,-6)]
  r=reconcile(a,entry_in=0,entry_out=1,entry_inout=2,history_complete=True)
  self.assertEqual(r["completed_positions"],1)
  self.assertEqual(r["consecutive_losses"],1)
  self.assertEqual(r["positions"][0]["net"],-11)
 def test_open_blocks_streak(self):
  r=reconcile([deal(10,1,0,1)],entry_in=0,entry_out=1,entry_inout=2,history_complete=True)
  self.assertIsNone(r["consecutive_losses"])
 def test_mixed_reversal_blocks(self):
  r=reconcile([deal(10,1,0,1),deal(10,2,2,2)],entry_in=0,entry_out=1,entry_inout=2,history_complete=True)
  self.assertIsNone(r["consecutive_losses"])
 def test_unknown_fee_blocks(self):
  x=deal(10,1,0,1);del x.fee
  with self.assertRaises(ValueError):reconcile([x],entry_in=0,entry_out=1,entry_inout=2,history_complete=True)
class Integrity(unittest.TestCase):
 def run_groups(self, rows, **kw):
  return reconcile(rows,entry_in=0,entry_out=1,entry_inout=2,**kw)
 def test_no_completeness_no_streak(self):
  r=self.run_groups([deal(10,1,0,1),deal(10,2,1,1,-5)])
  self.assertIsNone(r["consecutive_losses"])
 def test_duplicate_rejected(self):
  with self.assertRaises(ValueError):self.run_groups([deal(10,1,0,1)]*2)
 def test_exit_before_entry_unresolved(self):
  r=self.run_groups([deal(10,1,1,1),deal(10,2,0,1)],history_complete=True)
  self.assertIsNone(r["consecutive_losses"])
 def test_absent_open_position_unresolved(self):
  r=self.run_groups([],open_position_ids=[99],history_complete=True)
  self.assertEqual(r["unresolved_position_ids"],[99])
 def test_reuse_after_close_unresolved(self):
  r=self.run_groups([deal(10,1,0,1),deal(10,2,1,1),deal(10,3,0,1),deal(10,4,1,1)],history_complete=True)
  self.assertIsNone(r["consecutive_losses"])
 def test_three_losses_include_entry_costs(self):
  rows=[]
  for p in range(1,4):
   rows += [deal(p,p*3,0,1,fee=-2),deal(p,p*3+1,1,.5,1),deal(p,p*3+2,1,.5,0)]
  r=self.run_groups(list(reversed(rows)),history_complete=True)
  self.assertEqual(r["consecutive_losses"],3)
  self.assertTrue(r["loss_streak_stop"])
  self.assertEqual(len(r["positions"]),3)
 def test_breakeven_resets(self):
  r=self.run_groups([deal(1,1,0,1),deal(1,2,1,1,-1),deal(2,3,0,1),deal(2,4,1,1)],history_complete=True)
  self.assertEqual(r["consecutive_losses"],0)
 def test_out_by_not_silently_counted(self):
  with self.assertRaises(ValueError):self.run_groups([deal(10,1,3,1)])
if __name__=="__main__":unittest.main()
