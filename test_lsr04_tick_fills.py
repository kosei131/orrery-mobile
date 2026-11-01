import unittest
from lsr04_tick_fills import replay_exit
class TickFillTests(unittest.TestCase):
 def test_buy_spread_and_stop_gap(self):
  qs=[dict(time_msc=100,bid=99.9,ask=100.1),dict(time_msc=200,bid=98.8,ask=99.0)]
  a=replay_exit(qs,side="BUY",entry_after_msc=100,stop_price=99.5,target_price=102.)
  self.assertEqual(a["exit_reason"],"STOP")
  self.assertAlmostEqual(a["price_pnl_per_unit"],-1.3)
 def test_sell_ask_stop(self):
  qs=[dict(time_msc=100,bid=100.,ask=100.2),dict(time_msc=200,bid=101.1,ask=101.3)]
  a=replay_exit(qs,side="SELL",entry_after_msc=100,stop_price=101.,target_price=98.)
  self.assertEqual(a["exit_reason"],"STOP")
  self.assertAlmostEqual(a["price_pnl_per_unit"],-1.3)
 def test_sell_target(self):
  qs=[dict(time_msc=100,bid=100.,ask=100.2),dict(time_msc=200,bid=97.8,ask=98.)]
  a=replay_exit(qs,side="SELL",entry_after_msc=100,stop_price=101.,target_price=98.)
  self.assertEqual(a["exit_reason"],"TARGET")
  self.assertAlmostEqual(a["price_pnl_per_unit"],2.)
 def test_open_mark_and_no_future(self):
  q=[dict(time_msc=100,bid=99.9,ask=100.1)]
  self.assertEqual(replay_exit(q,side="BUY",entry_after_msc=100,stop_price=99.,target_price=102.)["status"],"OPEN")
  self.assertEqual(replay_exit(q,side="BUY",entry_after_msc=110,stop_price=99.,target_price=102.)["status"],"NO_ENTRY_QUOTE")
 def test_reject_crossed(self):
  with self.assertRaises(ValueError):
   replay_exit([dict(time_msc=100,bid=101,ask=100)],side="BUY",entry_after_msc=100,stop_price=99,target_price=102)
if __name__=="__main__":unittest.main()
