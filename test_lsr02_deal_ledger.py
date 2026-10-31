import unittest
from lsr02_deal_ledger import aggregate

def deal(ticket,position_id,entry,time_utc,volume,profit=0):
 return dict(ticket=ticket,position_id=position_id,entry=entry,time_utc=time_utc,
  volume=volume,profit=profit,commission=-1,swap=0,fee=0,symbol="XAUUSD")
class LedgerTests(unittest.TestCase):
 def test_partial_exit_and_averaging(self):
  x=aggregate([deal(4,10,"OUT",4,.5,40),deal(1,10,"IN",1,1),
               deal(3,10,"OUT",3,1,100),deal(2,10,"IN",2,.5)])
  p=x["completed"][0]
  self.assertAlmostEqual(p["net_pnl_usd"],136)
  self.assertEqual(p["exit_deals"],2)
  self.assertTrue(p["averaging_added"])
  self.assertAlmostEqual(p["max_simultaneous_lots"],1.5)
  self.assertFalse(x["execution_allowed"])
 def test_open_position_not_counted_as_closed(self):
  r=aggregate([deal(1,10,"IN",1,1)])
  self.assertEqual(len(r["completed"]),0)
  self.assertEqual(len(r["unclosed"]),1)
 def test_overexit_and_duplicate_rejected(self):
  with self.assertRaises(ValueError):aggregate([deal(1,10,"IN",1,1),deal(2,10,"OUT",2,2)])
  with self.assertRaises(ValueError):aggregate([deal(1,10,"IN",1,1),deal(1,10,"OUT",2,1)])
if __name__=="__main__":unittest.main()
