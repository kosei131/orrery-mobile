import unittest
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from lsr04_mt5_adaptive import capture_adaptive

class Mock:
 COPY_TICKS_ALL=1
 ACCOUNT_TRADE_MODE_DEMO=0
 def account_info(self):return SimpleNamespace(trade_mode=0)
 def symbol_info(self,s):return SimpleNamespace(trade_contract_size=100)
 def copy_ticks_range(self,s,a,b,f):
  if b-a>timedelta(hours=12):
   return [dict(time_msc=int((a+timedelta(seconds=i)).timestamp()*1000),
                bid=2000.,ask=2000.1) for i in range(3)]
  return [dict(time_msc=int((a+timedelta(seconds=1)).timestamp()*1000),
               bid=2000.,ask=2000.1)]

class AdaptiveTests(unittest.TestCase):
 def test_saturated_day_splits(self):
  a=datetime(2026,4,27,tzinfo=timezone.utc)
  out=capture_adaptive(Mock(),symbol="XAUUSD",start_utc=a,
                       end_utc=a+timedelta(days=1),cap=3)
  self.assertEqual(len(out["ticks"]),2)
  self.assertEqual(len(out["windows"]),2)
  self.assertFalse(out["execution_allowed"])
 def test_unsplittable_fails(self):
  a=datetime(2026,4,27,tzinfo=timezone.utc)
  with self.assertRaises(ValueError):
   capture_adaptive(Mock(),symbol="XAUUSD",start_utc=a,
                    end_utc=a+timedelta(seconds=30),cap=1,min_window_seconds=60)
 def test_wrong_account_fails(self):
  class Live(Mock):
   def account_info(self):return SimpleNamespace(trade_mode=2)
  a=datetime(2026,4,27,tzinfo=timezone.utc)
  with self.assertRaises(ValueError):
   capture_adaptive(Live(),symbol="XAUUSD",start_utc=a,end_utc=a+timedelta(hours=1))
if __name__=="__main__":unittest.main()
