"""Synthetic OHLC end-to-end paths; these are not market backtests."""
import random
import unittest
from lsr02_replay import replay
from test_lsr02_structure import bars


def fixture(sell=False):
    h=bars([(10,8,9),(12,9,11),(11,7,8),(14,10,13),(13,9,10),(16,12,15),(15,11,14)])
    f=bars([(14,12,13),(15,11,12),(14,12,13),(13,10,12),(14,11,13)])
    m=bars([(14,11,13)]*9)
    r=random.Random(2)  # Fixed synthetic fixture, not parameter/strategy optimization.
    for _ in range(16):
        o=r.uniform(11,15);c=r.uniform(11,15)
        m.append(dict(open=o,close=c,low=min(o,c)-.3,high=max(o,c)+.3,close_time=0))
    for stream,interval,start in ((h,14400,14400),(f,900,100800),(m,300,100800)):
        for i,b in enumerate(stream):
            b['close_time']=start+i*interval
            if sell:
                b.update(open=30-b['open'],close=30-b['close'],high=30-b['low'],low=30-b['high'])
    return h,f,m


def run(h,f,m,**kw):
    return replay('XAUUSD',h,f,m,as_of=m[-1]['close_time'],buffer=.1,lifetime=kw.get('lifetime',6000),left=1,right=1)


class PathTests(unittest.TestCase):
    def test_buy_sell_complete_structural_paths(self):
        for sell in (False,True):
            with self.subTest(sell=sell):
                h,f,m=fixture(sell);out=run(h,f,m)
                changes=[e['state'] for i,e in enumerate(out) if i==0 or e['state']!=out[i-1]['state']]
                self.assertEqual(changes,['SWEEP','CONFIRM','RETEST'])
                self.assertTrue(all(e['side']==('SELL' if sell else 'BUY') for e in out))
                self.assertTrue(all(e['readiness']=='BLOCKED_UNVERIFIED_GUARDS' for e in out))
                self.assertLess(out[0]['at'],next(e['at'] for e in out if e['state']=='CONFIRM'))
    def test_stop_and_deadline_win_over_retest(self):
        for sell in (False,True):
            h,f,m=fixture(sell)
            expired=run(h,f,m,lifetime=2400)
            self.assertEqual(expired[-1]['state'],'INVALID')
            self.assertNotIn('RETEST',[e['state'] for e in expired])
            if sell:m[-1]['high']=21
            else:m[-1]['low']=9
            self.assertEqual(run(h,f,m)[-1]['state'],'INVALID')
    def test_no_direction_no_candidate(self):
        h,f,m=fixture()
        for b in h:b.update(open=12,close=12,high=13,low=11)
        self.assertEqual(run(h,f,m),[])
    def test_both_paths_prefix_invariant(self):
        for sell in (False,True):
            h,f,m=fixture(sell);full=run(h,f,m)
            for n in range(1,len(m)+1):
                t=m[n-1]['close_time']
                actual=run([b for b in h if b['close_time']<=t],[b for b in f if b['close_time']<=t],m[:n])
                self.assertEqual(actual,[e for e in full if e['at']<=t])

if __name__=='__main__':unittest.main()
