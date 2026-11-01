import unittest
from lsr02_market_review import review_closed_bars
class ReviewTests(unittest.TestCase):
    def params(self):
        return dict(as_of=6000,interval=300,lookback=7,
            trend_efficiency=.3,range_efficiency=.1,spread_ok=True,
            news_clear=True,risk_budget_ok=True,loss_halt=False)
    def bars(self):
        return [dict(open=100,high=102,low=98,close=100,close_time=3900+300*i)
                for i in range(8)]
    def test_no_signal_is_never_promoted(self):
        r=review_closed_bars(self.bars(),**self.params())
        self.assertEqual(r["status"],"WAIT")
        self.assertIsNone(r["selected"])
        self.assertFalse(r["execution_allowed"])
    def test_stale_and_gap_defend(self):
        p=self.params();p["as_of"]=6900
        self.assertEqual(review_closed_bars(self.bars(),**p)["status"],"DEFENSE")
        b=self.bars();del b[3]
        self.assertEqual(review_closed_bars(b,**self.params())["reason_codes"],["INVALID_BAR_DATA"])
    def test_loss_halt_overrides_no_setup(self):
        p=self.params();p["loss_halt"]=True
        self.assertEqual(review_closed_bars(self.bars(),**p)["reason_codes"],["LOSS_HALT"])
    def test_spread_wait(self):
        p=self.params();p["spread_ok"]=False
        self.assertEqual(review_closed_bars(self.bars(),**p)["reason_codes"],["SPREAD_UNACCEPTABLE"])
if __name__=="__main__": unittest.main()
