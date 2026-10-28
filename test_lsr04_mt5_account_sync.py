import unittest
from datetime import datetime,timezone
from types import SimpleNamespace
from lsr04_mt5_account_sync import demo_day_check
class MT5:
 ACCOUNT_TRADE_MODE_DEMO=0
 DEAL_ENTRY_OUT=1
 def account_info(self):return SimpleNamespace(trade_mode=0,equity=10000)
 def positions_get(self):return []
 def history_deals_get(self,a,b):return []
class Tests(unittest.TestCase):
 def kw(self,**x):
  r=dict(day_start_utc=datetime(2026,10,27,tzinfo=timezone.utc),
         now_utc=datetime(2026,10,27,12,tzinfo=timezone.utc),
         day_start_equity=10000,existing_stop_risk=0,proposed_stop_risk=20)
  r.update(x);return r
 def test_no_streak_not_assumed_safe(self):
  a=demo_day_check(MT5(),**self.kw())
  self.assertEqual(a["status"],"BLOCKED_NO_AUTHORITATIVE_STREAK")
  self.assertFalse(a["execution_allowed"])
 def test_partial_deal_not_counted_as_trade(self):
  class Partial(MT5):
   def history_deals_get(self,a,b):return [SimpleNamespace(entry=1)]
  a=demo_day_check(Partial(),**self.kw())
  self.assertEqual(a["status"],"BLOCKED_TRADE_GROUPING_REQUIRED")
 def test_unavailable_history_blocks(self):
  class Missing(MT5):
   def history_deals_get(self,a,b):return None
  self.assertEqual(demo_day_check(Missing(),**self.kw())["status"],"BLOCKED_INCOMPLETE_BROKER_HISTORY")
 def test_real_account_rejected(self):
  class Live(MT5):
   def account_info(self):return SimpleNamespace(trade_mode=2,equity=10000)
  with self.assertRaises(ValueError):demo_day_check(Live(),**self.kw())
if __name__=="__main__":unittest.main()
