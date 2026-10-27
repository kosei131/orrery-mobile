import csv
from datetime import datetime,timezone
from pathlib import Path
import tempfile
import unittest
from lsr02_csv import load_csv,replay_csv,FIELDS

class CsvTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
    def file(self,tf='5m',**changes):
        r=dict(symbol='XAUUSD',timeframe=tf,source_id='SYNTHETIC_FIXTURE',close_time_utc='2026-01-01T04:00:00Z',open='100',high='101',low='99',close='100')
        r.update(changes);p=self.root/(tf+'.csv')
        with p.open('w',newline='',encoding='utf8') as f:
            w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerow(r)
        return p
    def test_valid_but_unverified_and_readonly(self):
        p=self.file();before=p.read_bytes()
        r=load_csv(p,symbol='XAUUSD',timeframe='5m',as_of=2e9)
        self.assertEqual(r['status'],'USER_PROVIDED_UNVERIFIED');self.assertEqual(len(r['sha256']),64)
        self.assertEqual(before,p.read_bytes())
    def test_invalid_inputs(self):
        for changes in [dict(close='nan'),dict(symbol='USDJPY'),dict(timeframe='15m'),dict(high='98'),dict(close_time_utc='2026-01-01T04:01:00Z'),dict(close_time_utc='2026-01-01T04:00:00'),dict(source_id='private value')]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                load_csv(self.file(**changes),symbol='XAUUSD',timeframe='5m',as_of=2e9)
        with self.assertRaises(ValueError):load_csv(self.file(),symbol='XAUUSD',timeframe='5m',as_of=0)
    def test_duplicates_rejected(self):
        p=self.file();lines=p.read_text().splitlines();p.write_text('\n'.join(lines+[lines[1]]))
        with self.assertRaises(ValueError):load_csv(p,symbol='XAUUSD',timeframe='5m',as_of=2e9)
    def test_bundle_never_authorizes_orders(self):
        paths={tf:self.file(tf) for tf in ('4H','15m','5m')}
        r=replay_csv(paths,symbol='XAUUSD',as_of=2e9,buffer=1,regime_config=dict(lookback=7,trend_efficiency=.3,range_efficiency=.1))
        self.assertFalse(r['execution_allowed']);self.assertEqual(r['trace'],[])
        self.file('15m',source_id='OTHER_SOURCE')
        with self.assertRaises(ValueError):replay_csv(paths,symbol='XAUUSD',as_of=2e9,buffer=1,regime_config={})

if __name__=='__main__':unittest.main()
