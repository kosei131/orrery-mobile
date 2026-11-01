import argparse
from datetime import datetime,timezone
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import mt5_local_dashboard as d

class QuoteTests(unittest.TestCase):
    def test_fresh_stale_invalid_and_missing(self):
        now=datetime.now(timezone.utc);ms=now.timestamp()*1000
        for tick,status in [(SimpleNamespace(bid=100,ask=101,time_msc=ms),'AVAILABLE'),(SimpleNamespace(bid=100,ask=101,time_msc=ms-11000),'STALE_OR_FUTURE'),(SimpleNamespace(bid=100,ask=101,time_msc=ms+1000),'STALE_OR_FUTURE'),(SimpleNamespace(bid=102,ask=101,time_msc=ms),'INVALID'),(None,'UNAVAILABLE'),(SimpleNamespace(bid=float('nan'),ask=101,time_msc=ms),'INVALID')]:
            with self.subTest(status=status),patch.object(d,'mt5',Mock(symbol_info_tick=Mock(return_value=tick))):
                r=d.read_quotes(now);self.assertEqual(len(r),2)
                self.assertEqual(r[0]['status'],status)
                if status!='AVAILABLE':self.assertNotIn('bid',r[0])
    def test_terminal_exception_redacted(self):
        with patch.object(d,'mt5',Mock(symbol_info_tick=Mock(side_effect=RuntimeError('PRIVATE')))):
            r=d.read_quotes(datetime.now(timezone.utc));self.assertNotIn('PRIVATE',str(r))
            self.assertEqual(r[0]['status'],'UNAVAILABLE')
    def test_account_switch_discards_snapshot(self):
        account=SimpleNamespace(trade_mode=0,login=1,server='DEMO')
        other=SimpleNamespace(trade_mode=2,login=2,server='REAL')
        mt5=Mock(ACCOUNT_TRADE_MODE_DEMO=0)
        mt5.account_info.side_effect=[account,other]
        mt5.positions_get.return_value=[];mt5.history_deals_get.return_value=[]
        with patch.object(d,'mt5',mt5),patch.object(d,'ARGS',argparse.Namespace(test_data=False)):
            with self.assertRaisesRegex(RuntimeError,'Account changed'):d.snapshot()
            mt5.shutdown.assert_called_once()

if __name__=='__main__':unittest.main()
