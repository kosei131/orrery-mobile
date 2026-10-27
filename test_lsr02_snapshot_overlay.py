import unittest
from datetime import datetime,timezone
from lsr02_snapshot_overlay import export_snapshot

NOW=30000
def snapshot():
    bars=[dict(time=NOW-i*300,open=100,high=101,low=99,close=100)
          for i in range(100,0,-1)]
    return dict(status="READ_ONLY_DEMO",
      checked_at_utc=datetime.fromtimestamp(NOW,timezone.utc).isoformat(),
      charts=[dict(symbol="XAUUSD",timeframe="5m",
                   status="CLOSED_BARS_AVAILABLE",bars=bars)])
class AdapterTests(unittest.TestCase):
    def test_valid_complete_candles(self):
        r=export_snapshot(snapshot(),symbol="XAUUSD",timeframe="5m",now=NOW)
        self.assertEqual(len(r["bars"]),100)
        self.assertEqual(r["cloud_location"],"INSIDE")
        self.assertEqual(r["status"],"WAIT")
        self.assertFalse(r["execution_allowed"])
    def test_fake_live_and_old_rejected(self):
        s=snapshot();s["status"]="LIVE"
        with self.assertRaises(ValueError):
            export_snapshot(s,symbol="XAUUSD",timeframe="5m",now=NOW)
        s=snapshot()
        with self.assertRaises(ValueError):
            export_snapshot(s,symbol="XAUUSD",timeframe="5m",now=NOW+6)
    def test_gap_and_duplicate_rejected(self):
        s=snapshot();s["charts"][0]["bars"].pop(5)
        with self.assertRaises(ValueError):
            export_snapshot(s,symbol="XAUUSD",timeframe="5m",now=NOW)
        s=snapshot();s["charts"].append(s["charts"][0])
        with self.assertRaises(ValueError):
            export_snapshot(s,symbol="XAUUSD",timeframe="5m",now=NOW)
if __name__=="__main__":unittest.main()
