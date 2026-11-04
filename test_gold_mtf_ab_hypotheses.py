import copy
import unittest
from orrery_gold_mtf_ab_hypotheses import candidate

def bar(t,lo,hi,op,cl):
    return {'close_time':t,'low':lo,'high':hi,'open':op,'close':cl}

def fixtures(kind='A'):
    h4=[bar(14400,80,110,105,105),bar(28800,90,120,105,105),
        bar(43200,100,130,105,105)]
    m15=[bar(t,105,115,110,110) for t in range(36900,43201,900)]
    m5=[]
    if kind=='A':
        m15.append(bar(44100,100,114,110,108))
        m5=[bar(t,105,110,108,108) for t in range(43500,44701,300)]
        m5.append(bar(45000,109,114,110,111))
    else:
        m15.append(bar(44100,105,125,112,110))
        m5=[bar(t,116,120,118,118) for t in range(43500,44701,300)]
        m5.append(bar(45000,113,119,118,114))
    return h4,m15,m5

class GoldMTFABTests(unittest.TestCase):
    def test_A_follows_h4_after_low_sweep(self):
        h,m,f=fixtures()
        s=candidate(h,m,f,as_of=45000)
        self.assertIsNotNone(s)
        self.assertEqual(s['family'],'A_CONTINUATION')
        self.assertEqual(s['side'],'BUY')
        self.assertFalse(s['execution_allowed'])
        self.assertIsNone(s['net_expectancy_r'])

    def test_B_counter_requires_outer_sweep(self):
        h,m,f=fixtures('B')
        s=candidate(h,m,f,as_of=45000)
        self.assertIsNotNone(s)
        self.assertEqual(s['family'],'B_COUNTER_SWEEP')
        self.assertEqual(s['side'],'SELL')

    def test_B_without_h4_extreme_touch_rejected(self):
        h,m,f=fixtures('B')
        m[-1]['high']=118
        self.assertIsNone(candidate(h,m,f,as_of=45000))

    def test_unclosed_h4_is_rejected(self):
        h,m,f=fixtures()
        h[-1]['close_time']=57600
        with self.assertRaises(ValueError):candidate(h,m,f,as_of=45000)

    def test_future_m15_is_rejected(self):
        h,m,f=fixtures()
        m.append(bar(45900,90,145,110,100))
        with self.assertRaises(ValueError):candidate(h,m,f,as_of=45000)

    def test_gap_is_rejected(self):
        h,m,f=fixtures()
        m[-2]['close_time']-=900
        with self.assertRaises(ValueError):candidate(h,m,f,as_of=45000)

    def test_m5_unconfirmed_cannot_pass(self):
        h,m,f=fixtures()
        f[-1]['close']=109
        self.assertIsNone(candidate(h,m,f,as_of=45000))

    def test_room_requirement_rejects(self):
        h,m,f=fixtures()
        h[-1]['high']=115
        self.assertIsNone(candidate(h,m,f,as_of=45000))

    def test_context_not_ready(self):
        h,m,f=fixtures()
        self.assertIsNone(candidate(h[:2],m,f,as_of=45000))

    def test_snapshot_not_mutated(self):
        h,m,f=fixtures()
        original=copy.deepcopy((h,m,f))
        candidate(h,m,f,as_of=45000)
        self.assertEqual((h,m,f),original)

if __name__=='__main__':
    unittest.main()
