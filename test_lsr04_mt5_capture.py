import unittest
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from lsr04_mt5_capture import capture_days
class Fake:
 COPY_TICKS_ALL=1
 ACCOUNT_TRADE_MODE_DEMO=0
 def account_info(self):return SimpleNamespace(trade_mode=0)
 def symbol_info(self,s):return SimpleNamespace(trade_contract_size=100)
 def copy_ticks_range(self,s,start,end,flag):
  t=int((start+timedelta(hours=1)).timestamp()*1000)
  return [dict(time_msc=t,bid=100.,ask=100.1)]
class CaptureTests(unittest.TestCase):
 def test_two_days(self):
  t=datetime(2026,4,27,tzinfo=timezone.utc)
  r=capture_days(Fake(),symbol="XAUUSD",start_utc=t,end_utc=t+timedelta(days=2))
  self.assertEqual(len(r["windows"]),2)
  self.assertEqual(len(r["ticks"]),2)
  self.assertFalse(r["execution_allowed"])
 def test_limit(self):
  t=datetime(2026,4,27,tzinfo=timezone.utc)
  with self.assertRaises(ValueError):capture_days(Fake(),symbol="XAUUSD",start_utc=t,end_utc=t+timedelta(days=200))
if __name__=="__main__":unittest.main()
