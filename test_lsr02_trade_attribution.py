import unittest
from lsr02_trade_attribution import report
def trade(id,gross,**kw):
 d=dict(id=id,symbol="XAUUSD",strategy="SCALP",opened_at=100,closed_at=130,
        gross_pnl_usd=gross,cost_usd=10,max_adverse_usd=30,
        max_favorable_usd=100,max_simultaneous_lots=1,
        averaging_added=False,support_confirmed=True,two_six_near=False,
        spread_widened=False,news_window=False,regime_changed=False)
 d.update(kw);return d
class AttributionTests(unittest.TestCase):
 def test_winners_losses_and_costs(self):
  r=report([trade("a",100),trade("b",-50,averaging_added=True),trade("c",15)],top_n=1)
  self.assertEqual(r["top_winners"][0]["id"],"a")
  self.assertEqual(r["top_losers"][0]["id"],"b")
  self.assertEqual(r["total_net_usd"],35)
  self.assertEqual(r["top_losers"][0]["cause_status"],"CORRELATION_ONLY_NOT_PROVEN")
  self.assertFalse(r["execution_allowed"])
 def test_invalid_and_missing_data_block(self):
  with self.assertRaises(ValueError):report([trade("a",1),trade("a",2)])
  a=trade("b",1);del a["news_window"]
  with self.assertRaises(ValueError):report([a])
if __name__=="__main__":unittest.main()
