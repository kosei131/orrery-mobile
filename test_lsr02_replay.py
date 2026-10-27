import unittest
from lsr02_replay import replay
from test_lsr02_structure import bars

class ReplayTests(unittest.TestCase):
    def test_empty_and_no_ready(self):
        self.assertEqual(replay('XAUUSD',[],[],[],as_of=0,buffer=1),[])
        data=bars([(10,8,9)]*8)
        self.assertEqual(replay('XAUUSD',[],[],data,as_of=2400,buffer=1),[])
    def test_reject_gaps_unfinished_and_bad_settings(self):
        data=bars([(10,8,9)]*3)
        with self.assertRaises(ValueError):replay('XAUUSD',[],[],data,as_of=300,buffer=1)
        with self.assertRaises(ValueError):replay('XAUUSD',[],[],data[::2],as_of=900,buffer=1)
        with self.assertRaises(ValueError):replay('XAUUSD',[],[],[],as_of=0,buffer=0)
    def test_real_detection_prefix_and_sweep_stop(self):
        h=bars([(10,8,9),(12,9,11),(11,7,8),(14,10,13),(13,9,10),(16,12,15),(15,11,14)])
        for i,b in enumerate(h):b['close_time']=(i+1)*14400
        start=100800
        f=bars([(14,12,13),(15,11,12),(14,12,13),(13,10,12),(14,11,13)])
        for i,b in enumerate(f):b['close_time']=start+i*900
        m=bars([(14,11,13)]*13)
        for i,b in enumerate(m):b['close_time']=start+i*300
        result=replay('XAUUSD',h,f,m,as_of=m[-1]['close_time'],buffer=.1,left=1,right=1)
        self.assertTrue(result)
        self.assertEqual(result[0]['side'],'BUY')
        self.assertAlmostEqual(result[0]['stop'],9.9)
        self.assertNotIn('READY',[e['state'] for e in result])
        for n in range(1,len(m)+1):
            t=m[n-1]['close_time']
            short=replay('XAUUSD',[b for b in h if b['close_time']<=t],[b for b in f if b['close_time']<=t],m[:n],as_of=t,buffer=.1,left=1,right=1)
            self.assertEqual(short,[e for e in result if e['at']<=t])

if __name__=='__main__':unittest.main()
