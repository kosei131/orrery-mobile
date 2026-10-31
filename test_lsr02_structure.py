import unittest
from lsr02_structure import detect

def bars(values):
    return [dict(open=c,close=c,high=h,low=l,close_time=(i+1)*300) for i,(h,l,c) in enumerate(values)]

class StructureTests(unittest.TestCase):
    def setUp(self):
        self.data=bars([(10,8,9),(12,9,10),(11,8,9),(13,9,11),(12,8,9),(14,10,13),(12,7,10)])
    def run_detect(self,b):
        return detect(b,as_of=b[-1]['close_time'],interval=300,left=1,right=1)
    def test_confirmation_delay_and_sweep(self):
        r=self.run_detect(self.data)
        p=next(x for x in r['pivots'] if x['index']==1 and x['kind']=='HIGH')
        self.assertEqual(p['known_at'],900)
        e=next(x for x in r['events'] if x['index']==3)
        self.assertEqual(e['kind'],'SWEEP')
        self.assertEqual(e['reference']['index'],1)
    def test_bos_choch_and_poi(self):
        data=bars([(10,8,9),(12,9,11),(11,7,8),(14,10,13),
                   (13,9,10),(16,12,15),(15,11,14),(18,13,17),(14,8,8.5)])
        data[7]['open']=16
        result=self.run_detect(data)
        self.assertTrue(any(e['kind']=='BOS' and e['direction']=='UP' for e in result['events']))
        change=next(e for e in result['events'] if e['kind']=='CHoCH')
        self.assertEqual(change['direction'],'DOWN')
        self.assertLess(change['poi']['index'],change['index'])
        self.assertEqual(change['poi']['known_at'],change['known_at'])

    def test_prefix_invariance(self):
        full=self.run_detect(self.data)
        for n in range(1,len(self.data)+1):
            prefix=self.run_detect(self.data[:n]);t=n*300
            for key in ('pivots','events'):
                self.assertEqual(prefix[key],[x for x in full[key] if x['known_at']<=t])
    def test_reject_incomplete_gap_and_nan(self):
        with self.assertRaises(ValueError):detect(self.data,as_of=300,interval=300)
        with self.assertRaises(ValueError):self.run_detect(self.data[:2]+self.data[3:])
        bad=[dict(self.data[0],close=float('nan'))]
        with self.assertRaises(ValueError):self.run_detect(bad)
    def test_equal_highs_not_strict_pivot(self):
        self.assertFalse(self.run_detect(bars([(10,8,9)]*4))['pivots'])

if __name__=='__main__': unittest.main()
