import sqlite3
import tempfile
import unittest
from pathlib import Path
from lsr02_halts import HaltStore
from lsr02_replay import replay
import test_lsr02_regime_replay as regime_tests

class HaltTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'orrery-halts.sqlite3'
    def test_reopen_and_explicit_ack(self):
        s=HaltStore(self.path,create=True);token=s.halt('XAUUSD',100)
        s=HaltStore(self.path);self.assertIsNotNone(s.get('XAUUSD'))
        self.assertIsNone(s.get('USDJPY'))
        self.assertFalse(s.acknowledge('XAUUSD','wrong'))
        self.assertTrue(s.acknowledge('XAUUSD',token));self.assertIsNone(s.get('XAUUSD'))
    def test_stale_ack_cannot_clear_new_halt(self):
        s=HaltStore(self.path,create=True);old=s.halt('XAUUSD',100);s.halt('XAUUSD',100)
        self.assertFalse(s.acknowledge('XAUUSD',old))
    def test_missing_corrupt_and_existing_creation_fail_closed(self):
        with self.assertRaises(sqlite3.Error):HaltStore(self.path)
        self.path.write_bytes(b'CORRUPTED')
        with self.assertRaises(sqlite3.Error):HaltStore(self.path)
        with self.assertRaises(FileExistsError):HaltStore(self.path,create=True)
        self.assertEqual(self.path.read_bytes(),b'CORRUPTED')
    def test_replay_persists_and_blocks_restart(self):
        s=HaltStore(self.path,create=True)
        h,f,m=regime_tests.RegimeReplayTests().streams()
        args=dict(as_of=m[-1]['close_time'],buffer=.1,lifetime=60000,left=1,right=1,regime_config=regime_tests.CONFIG)
        out=replay('XAUUSD',h,f,m,halt_store=s,**args)
        self.assertEqual(out[-1]['state'],'INVALID')
        with self.assertRaisesRegex(RuntimeError,'REVIEW_REQUIRED'):
            replay('XAUUSD',h,f,m,halt_store=HaltStore(self.path),**args)
    def test_deleted_file_not_recreated(self):
        s=HaltStore(self.path,create=True);s.halt('XAUUSD',100);self.path.unlink()
        with self.assertRaises(sqlite3.Error):s.get('XAUUSD')
        self.assertFalse(self.path.exists())

if __name__=='__main__':unittest.main()
