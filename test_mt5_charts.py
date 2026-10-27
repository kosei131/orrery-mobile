from datetime import datetime,timezone
import unittest
from unittest.mock import Mock,patch
import mt5_local_dashboard as d

class ChartTests(unittest.TestCase):
    def rows(self):return [dict(time=t,open=100,high=102,low=99,close=101) for t in (300,600,900)]
    def read(self,rows,now=1200):
        m=Mock(TIMEFRAME_M5=5);m.copy_rates_from_pos.return_value=rows
        with patch.object(d,'mt5',m):r=d.read_closed_charts(datetime.fromtimestamp(now,timezone.utc))
        m.copy_rates_from_pos.assert_any_call('XAUUSD',5,1,70)
        return r
    def test_closed_bars_and_start_index(self):
        r=self.read(self.rows());self.assertEqual(r[0]['status'],'CLOSED_BARS_AVAILABLE');self.assertEqual(len(r[0]['bars']),3)
    def test_future_gap_nan_and_stale_are_not_drawn(self):
        bad=self.rows();bad[1]['close']=float('nan')
        for rows,now in [(self.rows(),1100),(self.rows()[::2],1200),(bad,1200),(self.rows(),2000),(None,1200)]:
            with self.subTest(now=now):
                r=self.read(rows,now);self.assertNotEqual(r[0]['status'],'CLOSED_BARS_AVAILABLE');self.assertEqual(r[0]['bars'],[])

    def test_timeframes_are_independent_and_closed(self):
        m=Mock(TIMEFRAME_M5=5,TIMEFRAME_M15=15,TIMEFRAME_H4=240)
        intervals={5:300,15:900,240:14400}
        def rows(symbol,tf,start,count):
            self.assertEqual((start,count),(1,70))
            step=intervals[tf]
            return [dict(time=t,open=100,high=102,low=99,close=101) for t in (28800-2*step,28800-step)]
        m.copy_rates_from_pos.side_effect=rows
        with patch.object(d,'mt5',m):result=d.read_closed_charts(datetime.fromtimestamp(28800,timezone.utc))
        self.assertEqual(len(result),6)
        self.assertEqual({x['timeframe'] for x in result},{'5m','15m','4H'})
        self.assertTrue(all(x['status']=='CLOSED_BARS_AVAILABLE' for x in result))
        original=rows
        m.copy_rates_from_pos.side_effect=lambda symbol,tf,start,count:None if tf==15 else original(symbol,tf,start,count)
        with patch.object(d,'mt5',m):result=d.read_closed_charts(datetime.fromtimestamp(28800,timezone.utc))
        self.assertTrue(all((x['status']=='UNAVAILABLE')==(x['timeframe']=='15m') for x in result))

if __name__=='__main__':unittest.main()
