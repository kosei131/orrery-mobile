import csv,json,tempfile,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from orrery_xau_hypothetical_pnl import simulate

class PreGapAccountingTest(unittest.TestCase):
    def test_stop_hit_before_gap_is_counted_and_unresolved_is_censored(self):
        start=datetime(2026,6,1,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as d:
            m1=Path(d)/"m1.csv";event=Path(d)/"events.json"
            # BUY entry at 100.6 with stop 94.6, touch stop in minute 1.
            # One minute is missing afterward; old future-window logic dropped this loss.
            bars=[(0,100,101,99,100),(1,100,101,94,99),(3,100,101,99,100)]
            with m1.open("w",newline="") as f:
                w=csv.writer(f);w.writerow(["timestamp_utc","bid_open","bid_high","bid_low","bid_close"])
                for minute,o,h,l,c in bars:
                    w.writerow([(start+timedelta(minutes=minute)).isoformat(),o,h,l,c])
            event.write_text(json.dumps({"retouch_evidence":[{"first_poi_touch_close":int(start.timestamp()),"side":"BUY"}]}))
            result=simulate(m1,event,horizon_mins=4)
            self.assertEqual(result["trades"],1)
            self.assertEqual(result["losers"],1)
            self.assertEqual(result["skipped_incomplete"],0)
            self.assertAlmostEqual(result["trades_detail"][0]["r"],-1.0)
            # No barrier before gap: cannot claim any exit or liquidation.
            bars[1]=(1,100,101,99,100)
            with m1.open("w",newline="") as f:
                w=csv.writer(f);w.writerow(["timestamp_utc","bid_open","bid_high","bid_low","bid_close"])
                for minute,o,h,l,c in bars:
                    w.writerow([(start+timedelta(minutes=minute)).isoformat(),o,h,l,c])
            result=simulate(m1,event,horizon_mins=4)
            self.assertEqual(result["trades"],0)
            self.assertEqual(result["skipped_incomplete"],1)
if __name__=="__main__":unittest.main()
