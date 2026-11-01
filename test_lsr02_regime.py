import unittest
from lsr02_regime import classify,review_transition
from test_lsr02_structure import bars

class RegimeTests(unittest.TestCase):
    def classify(self,b,**kw):
        return classify(b,as_of=kw.get('as_of',b[-1]['close_time'] if b else 0),interval=300,lookback=7,trend_efficiency=.3,range_efficiency=.2,left=1,right=1)
    def test_up_down_symmetry(self):
        b=bars([(10,8,9),(12,9,11),(11,7,8),(14,10,13),(13,9,10),(16,12,15),(15,11,15)])
        self.assertEqual(self.classify(b)['regime'],'UP')
        mirror=[dict(open=30-x['open'],close=30-x['close'],high=30-x['low'],low=30-x['high'],close_time=x['close_time']) for x in b]
        self.assertEqual(self.classify(mirror)['regime'],'DOWN')
        self.assertFalse(self.classify(b)['execution_allowed'])
    def test_range_not_trade_permission(self):
        b=bars([(11,9,10),(13,10,12),(10,7,8),(13,10,12),(10,7,8),(13,10,12),(11,9,10)])
        r=self.classify(b);self.assertEqual(r['regime'],'RANGE_CANDIDATE');self.assertFalse(r['execution_allowed'])
    def test_missing_flat_stale(self):
        self.assertEqual(self.classify([])['regime'],'UNKNOWN')
        b=bars([(11,9,10)]*7)
        self.assertEqual(self.classify(b)['regime'],'UNKNOWN')
        self.assertEqual(self.classify(b,as_of=2400)['reason'],'STALE_DATA')
        with self.assertRaises(ValueError):self.classify(b[::2])
    def test_transitions_do_not_enable_trading(self):
        for prev in ('UNKNOWN','UP','DOWN','RANGE_CANDIDATE'):
            self.assertEqual(review_transition(prev,'UNKNOWN'),'CANCEL_CANDIDATE_AND_WAIT')
        self.assertEqual(review_transition('UP','DOWN'),'CANCEL_CANDIDATE_AND_REVIEW')
        self.assertEqual(review_transition('UP','UP'),'RECHECK_RISK_NO_AUTO_RESUME')

if __name__=='__main__':unittest.main()
