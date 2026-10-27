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

if __name__=='__main__':unittest.main()
