import unittest
from types import SimpleNamespace
from lsr04_mt5_broker_quote import demo_stop_sizing
class MT5:
 ACCOUNT_TRADE_MODE_DEMO=0
 ORDER_TYPE_BUY=0
 ORDER_TYPE_SELL=1
 def account_info(self):return SimpleNamespace(trade_mode=0,currency="USD",equity=10000)
 def symbol_info(self,s):return SimpleNamespace(volume_min=.01,volume_max=10,volume_step=.01)
 def order_calc_profit(self,side,symbol,volume,entry,stop):
  return -200 if (side==0 and stop<entry) or (side==1 and stop>entry) else 200
class Tests(unittest.TestCase):
 def test_demo_buy(self):
  a=demo_stop_sizing(MT5(),symbol="XAUUSD",side="BUY",entry_price=2000,stop_price=1999)
  self.assertEqual(a["lots"],.25)
  self.assertFalse(a["execution_allowed"])
 def test_demo_sell(self):
  a=demo_stop_sizing(MT5(),symbol="USDJPY",side="SELL",entry_price=150,stop_price=151)
  self.assertEqual(a["lots"],.25)
 def test_real_rejected(self):
  class Live(MT5):
   def account_info(self):return SimpleNamespace(trade_mode=2,currency="USD",equity=10000)
  with self.assertRaises(ValueError):
   demo_stop_sizing(Live(),symbol="XAUUSD",side="BUY",entry_price=2000,stop_price=1999)
if __name__=="__main__":unittest.main()
