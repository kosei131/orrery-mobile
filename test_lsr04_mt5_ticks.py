import unittest
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
from lsr04_mt5_ticks import read_ticks
class Mock:
 COPY_TICKS_ALL=1
 ACCOUNT_TRADE_MODE_DEMO=0
 def account_info(self):return SimpleNamespace(trade_mode=0)
 def symbol_info(self,s):return SimpleNamespace(trade_contract_size=100)
 def copy_ticks_range(self,s,a,b,flag):
  return [dict(time_msc=int((a+timedelta(seconds=1)).timestamp()*1000),bid=2000.,ask=2000.2)]
class TickTests(unittest.TestCase):
 def bounds(self):
  s=datetime(2026,4,27,tzinfo=timezone.utc)
  return dict(mt5=Mock(),account_is_demo=True,symbol="XAUUSD",start_utc=s,end_utc=s+timedelta(minutes=5))
 def test_readonly(self):
  x=read_ticks(**self.bounds())
  self.assertEqual(x["count"],1)
  self.assertFalse(x["execution_allowed"])
 def test_live_refused(self):
  with self.assertRaises(ValueError):read_ticks(**dict(self.bounds(),account_is_demo=False))
 def test_live_broker_mode_refused(self):
  class Live(Mock):
   def account_info(self):return SimpleNamespace(trade_mode=2)
  with self.assertRaises(ValueError):read_ticks(**dict(self.bounds(),mt5=Live()))
 def test_crossed_quotes_refused(self):
  class Bad(Mock):
   def copy_ticks_range(self,s,a,b,f):
    return [dict(time_msc=int((a+timedelta(seconds=1)).timestamp()*1000),bid=5.,ask=4.)]
  with self.assertRaises(ValueError):read_ticks(**dict(self.bounds(),mt5=Bad()))
if __name__=="__main__":unittest.main()
