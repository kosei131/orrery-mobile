from copy import deepcopy
from datetime import datetime,timezone
import unittest
from lsr02_mt5_bridge import review_snapshot

BASE=1767225600  # 2026-01-01 00:00 UTC
NOW=BASE+28800
CONFIG=dict(lookback=7,trend_efficiency=.3,range_efficiency=.1)
def sample():
    charts=[]
    for tf,step,count in [('4H',14400,2),('15m',900,32),('5m',300,70)]:
        bars=[dict(time=NOW-i*step,open=100,close=100,high=101,low=99) for i in range(count,0,-1)]
        charts.append(dict(symbol='XAUUSD',timeframe=tf,status='CLOSED_BARS_AVAILABLE',bars=bars))
    return dict(status='READ_ONLY_DEMO',checked_at_utc=datetime.fromtimestamp(NOW,timezone.utc).isoformat(),charts=charts)

def run(s,now=NOW):return review_snapshot(s,symbol='XAUUSD',now=now,buffer=1,regime_config=CONFIG)

class BridgeTests(unittest.TestCase):
    def test_consistent_data_reaches_replay_without_order_permission(self):
        s=sample();before=deepcopy(s);r=run(s)
        self.assertEqual(r['status'],'RESEARCH_REPLAY_ONLY');self.assertFalse(r['execution_allowed'])
        self.assertEqual(s,before);self.assertEqual(r['trace'],[])
    def test_extended_100_bar_window_accepted_101_rejected(self):
        s=sample()
        now=NOW
        five=next(c for c in s['charts'] if c['timeframe']=='5m')
        five['bars']=[dict(time=now-i*300,open=100,close=100,high=101,low=99)
                      for i in range(100,0,-1)]
        r=run(s)
        self.assertEqual(r['status'],'RESEARCH_REPLAY_ONLY')
        self.assertFalse(r['execution_allowed'])
        five['bars'].insert(0,dict(time=now-101*300,open=100,close=100,high=101,low=99))
        r=run(s)
        self.assertEqual(r['status'],'NOT_EVALUATED')
        self.assertFalse(r['execution_allowed'])

    def test_simulation_and_stale_snapshot_blocked(self):
        s=sample();s['status']='SIMULATED_TEST_DATA';self.assertEqual(run(s)['status'],'NOT_EVALUATED')
        self.assertEqual(run(sample(),NOW+6)['status'],'NOT_EVALUATED')
    def test_cross_timeframe_mismatch_blocked(self):
        s=sample();s['charts'][1]['bars'][-1]['high']=105
        self.assertEqual(run(s)['status'],'NOT_EVALUATED')
    def test_missing_duplicate_future_and_gap_blocked(self):
        for mode in ('missing','duplicate','future','gap'):
            s=sample()
            if mode=='missing':s['charts'].pop()
            elif mode=='duplicate':s['charts'].append(deepcopy(s['charts'][0]))
            elif mode=='future':s['charts'][-1]['bars'][-1]['time']+=300
            else:s['charts'][-1]['bars'].pop(10)
            with self.subTest(mode=mode):self.assertEqual(run(s)['status'],'NOT_EVALUATED')

if __name__=='__main__':unittest.main()
