"""Integration with real synthetic OHLC classification; no feed/order calls."""
import unittest
from lsr02_replay import replay
from test_lsr02_paths import fixture

CONFIG=dict(lookback=7,trend_efficiency=.2,range_efficiency=.1)

def walk(h,f,m,config=CONFIG):
    return replay('XAUUSD',h,f,m,as_of=m[-1]['close_time'],buffer=.1,lifetime=60000,left=1,right=1,regime_config=config)

class RegimeReplayTests(unittest.TestCase):
    def streams(self,sell=False,change=True):
        h,f,m=fixture(sell)
        while m[-1]['close_time']<116400:
            m.append(dict(m[-1],close_time=m[-1]['close_time']+300))
        if change:
            b=dict(open=14,high=15,low=10,close=11,close_time=115200)
            if sell:b.update(open=16,high=20,low=15,close=19)
            h.append(b)
        return h,f,m
    def test_changed_environment_cancels_both_sides(self):
        for sell in (False,True):
            h,f,m=self.streams(sell)
            out=walk(h,f,m)
            self.assertEqual(out[0]['state'],'SWEEP')
            self.assertIn('RETEST',[x['state'] for x in out])
            self.assertEqual(out[-1]['state'],'INVALID')
            self.assertEqual(out[-1]['at'],115200)
            self.assertEqual(out[-1]['reason'],'REGIME_REVIEW_REQUIRED')
            self.assertEqual(out[-1]['regime'],'UNKNOWN')
            self.assertNotIn('READY',[x['state'] for x in out])
    def test_stale_context_also_cancels(self):
        h,f,m=self.streams(change=False)
        out=walk(h,f,m)
        self.assertEqual(out[-1]['regime_reason'],'STALE_DATA')
    def test_insufficient_context_blocks_creation(self):
        h,f,m=self.streams()
        self.assertEqual(walk(h,f,m,dict(CONFIG,lookback=99)),[])
    def test_future_context_does_not_rewrite_history(self):
        h,f,m=self.streams();full=walk(h,f,m)
        for n in range(1,len(m)+1):
            t=m[n-1]['close_time']
            prefix=walk([b for b in h if b['close_time']<=t],[b for b in f if b['close_time']<=t],m[:n])
            self.assertEqual(prefix,[e for e in full if e['at']<=t])
    def test_invalid_config_rejected(self):
        h,f,m=fixture()
        with self.assertRaises(ValueError):walk(h,f,m,{})

if __name__=='__main__':unittest.main()
