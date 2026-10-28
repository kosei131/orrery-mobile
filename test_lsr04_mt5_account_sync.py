import unittest
from datetime import datetime,timezone
from types import SimpleNamespace
from lsr04_mt5_account_sync import demo_day_check
class MT5:
 ACCOUNT_TRADE_MODE_DEMO=0
 DEAL_ENTRY_IN=0
 DEAL_ENTRY_OUT=1
 DEAL_ENTRY_INOUT=2
 DEAL_TYPE_BUY=0
 DEAL_TYPE_SELL=1
 def account_info(self):return SimpleNamespace(trade_mode=0,equity=10000,login=1,server="demo",currency="USD")
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
  self.assertEqual(a["status"],"BLOCKED_UNCLASSIFIED_OR_INVALID_HISTORY")
 def test_unavailable_history_blocks(self):
  class Missing(MT5):
   def history_deals_get(self,a,b):return None
  self.assertEqual(demo_day_check(Missing(),**self.kw())["status"],"BLOCKED_INCOMPLETE_BROKER_HISTORY")
 def test_real_account_rejected(self):
  class Live(MT5):
   def account_info(self):return SimpleNamespace(trade_mode=2,equity=10000)
  with self.assertRaises(ValueError):demo_day_check(Live(),**self.kw())
class Bridge(unittest.TestCase):
 kw=Tests.kw
 def row(self,p,t,entry,volume=1,profit=0):
  return SimpleNamespace(position_id=p,ticket=t,time_msc=int(datetime(2026,10,27,1,tzinfo=timezone.utc).timestamp()*1000)+t,
   entry=entry,type=0 if entry==0 else 1,symbol="XAUUSD",volume=volume,profit=profit,commission=-1,swap=0,fee=0)
 def broker(self,rows,positions=()):
  class Broker(MT5):
   def history_deals_get(self,a,b):self.bounds=(a,b);return rows
   def positions_get(self):return positions
  return Broker()
 def test_three_losses_connect_to_gate(self):
  rows=[]
  for p in range(1,4):rows += [self.row(p,p*2,0),self.row(p,p*2+1,1,profit=-10)]
  b=self.broker(rows)
  start=datetime(2026,10,1,tzinfo=timezone.utc)
  r=demo_day_check(b,**self.kw(history_start_utc=start,history_complete=True))
  self.assertEqual(b.bounds[0],start)
  self.assertEqual(r["grouping"]["consecutive_losses"],3)
  self.assertIn("LOSS_STREAK_STOP",r["risk_review"]["reasons"])
  self.assertEqual(r["daily_deal_net"],-36)
  self.assertFalse(r["execution_allowed"])
 def test_overnight_entry_cost_not_in_daily_total(self):
  a=self.row(1,1,0);a.time_msc-=86400000
  r=demo_day_check(self.broker([a,self.row(1,2,1,profit=10)]),**self.kw(history_start_utc=datetime(2026,10,26,tzinfo=timezone.utc),history_complete=True))
  self.assertEqual(r["daily_deal_net"],9)
  self.assertEqual(r["grouping"]["positions"][0]["net"],8)
  self.assertEqual(r["status"],"BLOCKED_DAILY_RECONCILIATION")
  self.assertFalse(r["daily_reconciled"])
 def test_partial_exit_not_a_loss(self):
  r=demo_day_check(self.broker([self.row(1,1,0),self.row(1,2,1,.4,-5)], [SimpleNamespace(identifier=1)]),**self.kw(history_complete=True))
  self.assertIsNone(r["grouping"]["consecutive_losses"])
 def test_cash_operation_blocks(self):
  row=self.row(1,1,0);row.type=2
  self.assertEqual(demo_day_check(self.broker([row]),**self.kw())["status"],"BLOCKED_UNCLASSIFIED_OR_INVALID_HISTORY")
 def test_account_switch_discards(self):
  class Switch(MT5):
   calls=0
   def account_info(self):
    a=super().account_info();self.calls+=1;a.login=self.calls;return a
  self.assertEqual(demo_day_check(Switch(),**self.kw())["status"],"BLOCKED_ACCOUNT_CHANGED")
 def test_truncated_entry_blocks(self):
  r=demo_day_check(self.broker([self.row(1,2,1,profit=-5)]),**self.kw(history_complete=True))
  self.assertEqual(r["status"],"BLOCKED_UNCLASSIFIED_OR_INVALID_HISTORY")
 def test_wrong_direction_blocks(self):
  a=self.row(1,2,1);a.type=0
  r=demo_day_check(self.broker([self.row(1,1,0),a]),**self.kw(history_complete=True))
  self.assertEqual(r["status"],"BLOCKED_UNCLASSIFIED_OR_INVALID_HISTORY")
 def test_read_exception_blocks(self):
  class Broken(MT5):
   def positions_get(self):raise RuntimeError("offline")
  self.assertEqual(demo_day_check(Broken(),**self.kw())["status"],"BLOCKED_BROKER_READ_FAILED")
 def test_missing_fee_blocks(self):
  a=self.row(1,1,0);del a.fee
  self.assertEqual(demo_day_check(self.broker([a]),**self.kw())["status"],"BLOCKED_UNCLASSIFIED_OR_INVALID_HISTORY")
 def test_future_deal_blocks(self):
  a=self.row(1,1,0);a.time_msc+=86400000
  self.assertEqual(demo_day_check(self.broker([a]),**self.kw())["status"],"BLOCKED_UNCLASSIFIED_OR_INVALID_HISTORY")
 def test_duplicate_history_blocks(self):
  a=self.row(1,1,0)
  self.assertEqual(demo_day_check(self.broker([a,a]),**self.kw())["status"],"BLOCKED_UNCLASSIFIED_OR_INVALID_HISTORY")
 def test_nonfinite_equity_blocks(self):
  class Bad(MT5):
   def account_info(self):
    a=super().account_info();a.equity=float("nan");return a
  self.assertEqual(demo_day_check(Bad(),**self.kw())["status"],"BLOCKED_INVALID_ACCOUNT_RISK")
 def test_unasserted_complete_trade_has_unknown_streak(self):
  r=demo_day_check(self.broker([self.row(1,1,0),self.row(1,2,1,profit=-5)]),**self.kw())
  self.assertIsNone(r["grouping"]["consecutive_losses"])
  self.assertEqual(r["status"],"BLOCKED_NO_AUTHORITATIVE_STREAK")
if __name__=="__main__":unittest.main()
