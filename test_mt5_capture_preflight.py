from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import unittest

from lsr04_tick_archive import _encode
from orrery_mt5_candidate_probe import _request
from orrery_mt5_capture_preflight import preflight
from orrery_mt5_probe_verify import PROBE_SOURCES,HISTORY_SOURCES
from test_mt5_candidate_probe import ProbeTests

class OfflinePreflightTests(unittest.TestCase):
    def setUp(self):
        f=ProbeTests();f.setUp();self.addCleanup(f.doCleanups);self.f=f
        self.prepared=f.root/'prepared.json'
        request=_request(f.path,f.pin,f.now)
        request['required_python_source_sha256']={
            name:sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in PROBE_SOURCES|HISTORY_SOURCES
        }
        self.prepared.write_bytes(_encode(request))
        self.prepared_pin=sha256(self.prepared.read_bytes()).hexdigest()
        self.terminal=f.root/'terminal64.exe';self.terminal.write_bytes(b'fake demo path for unit test only')

    def check(self,**changes):
        args=dict(prepared_request=self.prepared,request_sha256=self.prepared_pin,
                  terminal_path=self.terminal,output=self.f.output,now=self.f.now)
        args.update(changes)
        return preflight(self.f.path,self.f.pin,**args)

    def test_matching_pins_and_existing_terminal_are_read_only_and_not_approval(self):
        original=self.prepared.read_bytes()
        result=self.check()
        self.assertEqual(result['status'],'OFFLINE_PREFLIGHT_OK_NOT_DEMO_AUTHENTICATED')
        self.assertFalse(result['execution_allowed'])
        self.assertFalse(result['history_captured'])
        self.assertIsNone(result['actual_profit_usd'])
        self.assertFalse(self.f.output.exists())
        self.assertEqual(self.prepared.read_bytes(),original)

    def test_unpinned_reference_is_rejected(self):
        self.f.path.write_bytes(self.f.path.read_bytes()+b' ')
        with self.assertRaises(ValueError):self.check()

    def test_changed_prepared_request_is_rejected(self):
        self.prepared.write_bytes(self.prepared.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'pin mismatch'):self.check()

    def test_wrong_candidate_with_fresh_request_hash_is_rejected(self):
        from lsr04_tick_archive import _decode
        request=_decode(self.prepared.read_bytes())
        request['candidate_id']='XAUUSD:forged:BUY'
        self.prepared.write_bytes(_encode(request))
        with self.assertRaisesRegex(ValueError,'differs'):
            self.check(request_sha256=sha256(self.prepared.read_bytes()).hexdigest())

    def test_missing_terminal_and_existing_output_are_rejected(self):
        with self.assertRaises(ValueError):self.check(terminal_path=self.f.root/'not-found.exe')
        self.f.output.mkdir()
        with self.assertRaises(ValueError):self.check()

if __name__=='__main__':
    unittest.main()
