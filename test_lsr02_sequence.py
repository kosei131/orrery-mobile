import unittest
from lsr02_sequence import Candidate

class SequenceTests(unittest.TestCase):
    def candidate(self):return Candidate('XAUUSD','BUY',0,2000,0,'UP',95,1)
    def step(self,c,t,tf='5m',**extra):
        e=dict(data_ok=True,context_valid=True,news_clear=True,spread_ok=True);e.update(extra)
        return c.step(symbol='XAUUSD',timeframe=tf,closed_at=t,bar=dict(open=100,high=102,low=99,close=101),evidence=e)
    def test_complete_and_expire(self):
        c=self.candidate()
        self.assertEqual(self.step(c,300,'15m',sweep_closed=True),'SWEEP')
        self.assertEqual(self.step(c,600,structure_closed=True,poi=(99,100)),'CONFIRM')
        self.assertEqual(self.step(c,900,risk_checked=True),'RETEST')
        self.assertEqual(self.step(c,1200,risk_checked=True),'READY')
        self.assertEqual(self.step(c,2100,risk_checked=True),'INVALID')
        self.assertEqual(len(c.audit),5)
    def test_no_skip_and_missing_guards(self):
        c=self.candidate()
        self.assertEqual(self.step(c,300,structure_closed=True,risk_checked=True),'WATCH')
        self.assertEqual(self.step(c,600,data_ok=False),'INVALID')
        self.assertEqual(self.step(c,900,sweep_closed=True),'INVALID')
    def test_duplicate_and_bad_context(self):
        c=self.candidate();self.step(c,300)
        with self.assertRaises(ValueError):self.step(c,300)
        with self.assertRaises(ValueError):Candidate('XAUUSD','BUY',0,2000,1,'UP',95,1)
    def test_stop_before_retest(self):
        c=self.candidate()
        self.assertEqual(c.step(symbol='XAUUSD',timeframe='5m',closed_at=300,bar=dict(open=95,high=100,low=93,close=99),evidence={}), 'INVALID')

if __name__=='__main__':unittest.main()
