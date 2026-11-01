# SPDX-License-Identifier: GPL-3.0-only
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from lsr05_halftrend import calculate
from lsr05_observation_store import create_store, append_snapshot, restore_store
from lsr04_tick_archive import _decode, _encode
from orrery_research_worker import worker_lock
from test_lsr05_halftrend import bars


class ObservationStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'private store'
        self.data=bars([100.]*100)

    def create(self,**settings):
        return create_store(self.root,**settings)['head_sha256']

    def append(self,pin,data=None,observed_at=31000):
        data=self.data if data is None else data
        snapshot=calculate(data,as_of=data[-1]['close_time'],interval=300,enabled=True)
        return append_snapshot(self.root,expected_head_sha256=pin,snapshot=snapshot,symbol='XAUUSD',
            observed_at=observed_at,data_source='SYNTHETIC',implementation_version='v1')

    def test_empty_store_and_first_append_restore(self):
        pin=self.create()
        self.assertEqual(restore_store(self.root,expected_head_sha256=pin)['batches'],0)
        saved=self.append(pin)
        restored=restore_store(self.root,expected_head_sha256=saved['head_sha256'])
        self.assertEqual(restored['batches'],1)
        self.assertEqual(len(restored['report']['events']),100)
        self.assertFalse(restored['nonrepainting_verified']); self.assertFalse(restored['execution_allowed'])

    def test_restart_keeps_revision_detection(self):
        pin=self.create(); first=self.append(pin)
        changed=deepcopy(self.data); changed[70]['high']=100.7
        second=self.append(first['head_sha256'],changed,observed_at=31001)
        restored=restore_store(self.root,expected_head_sha256=second['head_sha256'])
        self.assertGreater(restored['report']['value_revision_count'],0)
        self.assertEqual(restored['report']['signal_revision_count'],0)

    def test_identical_snapshot_after_restart_not_new_signals(self):
        pin=self.create(); first=self.append(pin)
        second=self.append(first['head_sha256'],observed_at=31001)
        restored=restore_store(self.root,expected_head_sha256=second['head_sha256'])
        self.assertEqual(len(restored['report']['events']),100)
        self.assertEqual(len(restored['report']['signal_events']),1)
        self.assertEqual(restored['report']['last_seen_scopes'][0]['observed_at'],31001)

    def test_stale_writer_cannot_append_or_silently_roll_back(self):
        pin=self.create(); self.append(pin)
        with self.assertRaises(ValueError): self.append(pin,observed_at=31001)
        with self.assertRaises(ValueError): restore_store(self.root,expected_head_sha256=pin)
        self.assertFalse((self.root/'batch-000001').exists())

    def test_payload_tamper_rejected(self):
        pin=self.create(); saved=self.append(pin)
        (self.root/'batch-000000'/'result.json').write_bytes(b'{}\n')
        with self.assertRaises(ValueError): restore_store(self.root,expected_head_sha256=saved['head_sha256'])

    def test_reanchored_tampered_result_still_fails_replay(self):
        pin=self.create(); self.append(pin)
        folder=self.root/'batch-000000'
        result=_decode((folder/'result.json').read_bytes()); result['unchanged_rows']=100
        data=_encode(result); (folder/'result.json').write_bytes(data)
        marker=_decode((folder/'complete.json').read_bytes()); marker['result_sha256']=sha256(data).hexdigest()
        marker_bytes=_encode(marker); (folder/'complete.json').write_bytes(marker_bytes)
        with self.assertRaises(ValueError): restore_store(self.root,expected_head_sha256=sha256(marker_bytes).hexdigest())

    def test_interrupted_write_has_no_valid_completion(self):
        pin=self.create()
        import lsr05_observation_store as module
        writer=module._write_exclusive
        def fail(path,data):
            if path.name=='result.json': raise OSError('synthetic interruption')
            writer(path,data)
        with patch.object(module,'_write_exclusive',side_effect=fail):
            with self.assertRaises(OSError): self.append(pin)
        self.assertFalse((self.root/'batch-000000'/'complete.json').exists())
        with self.assertRaises(ValueError): restore_store(self.root,expected_head_sha256=pin)

    def test_batch_capacity_and_invalid_snapshot_leave_no_partial_batch(self):
        pin=self.create(max_batches=1); first=self.append(pin)
        with self.assertRaises(ValueError): self.append(first['head_sha256'],observed_at=31001)
        self.assertFalse((self.root/'batch-000001').exists())

    def test_event_capacity_stops_before_disk_write(self):
        pin=self.create(max_events=99)
        with self.assertRaises(ValueError): self.append(pin)
        self.assertFalse((self.root/'batch-000000').exists())

    def test_single_owner_lock_reused(self):
        pin=self.create()
        with worker_lock(self.root):
            with self.assertRaises(OSError): self.append(pin)
        self.assertFalse((self.root/'batch-000000').exists())

    def test_missing_batch_or_unexpected_files_rejected(self):
        pin=self.create(); saved=self.append(pin)
        (self.root/'note.txt').write_text('unexpected')
        with self.assertRaises(ValueError): restore_store(self.root,expected_head_sha256=saved['head_sha256'])

    def test_changed_implementation_does_not_restore_as_old_version(self):
        pin=self.create()
        with patch('lsr05_observation_store._code_pins',return_value={}):
            with self.assertRaises(ValueError): restore_store(self.root,expected_head_sha256=pin)

    def test_existing_store_never_overwritten(self):
        pin=self.create(); before=(self.root/'store.json').read_bytes()
        with self.assertRaises(FileExistsError): self.create()
        self.assertEqual((self.root/'store.json').read_bytes(),before)
        self.assertEqual(restore_store(self.root,expected_head_sha256=pin)['batches'],0)

    def test_unrelated_folder_is_not_given_a_store_lock(self):
        self.root.mkdir()
        with self.assertRaises(ValueError): restore_store(self.root,expected_head_sha256='0'*64)
        self.assertFalse((self.root/'worker.lock').exists())


if __name__=='__main__': unittest.main()
