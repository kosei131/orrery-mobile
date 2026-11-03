from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from test_halftrend_holdout import plan, encoded
from test_halftrend_holdout_batch import segment
from orrery_prospective_panel import replay_panel, load_panel


def synthetic_panel():
    raw,pin=encoded(plan())
    r=replay_panel([segment(86400),segment(115200)],raw,plan_sha256=pin,
                   now=datetime(1970,2,1,tzinfo=timezone.utc))
    r['manifest_sha256']='0'*64
    return r


class ProspectivePanelTests(unittest.TestCase):
    def test_real_engine_synthetic_zip_has_unknown_costs_and_all_groups(self):
        r=synthetic_panel()
        self.assertEqual(len(r['segments']),2)
        self.assertEqual(len(r['summaries']),5)
        self.assertEqual(r['summaries']['LSR02']['candidates'],0)
        self.assertTrue(r['partial_period']);self.assertTrue(r['boundary_state_reset'])
        self.assertFalse(r['continuous_strategy_equivalence_verified'])
        self.assertIsNone(r['net_expectancy_r']);self.assertFalse(r['execution_allowed'])
        self.assertNotIn('candidates',r);self.assertNotIn('reports',r)
    def test_existing_gate_rejects_overlaps_old_period_and_future(self):
        raw,pin=encoded(plan());a=segment(86400)
        for items,now in (([a,a],datetime(1970,2,1,tzinfo=timezone.utc)),
                          ([segment(0)],datetime(1970,2,1,tzinfo=timezone.utc)),
                          ([a],datetime(1970,1,1,tzinfo=timezone.utc))):
            with self.subTest(items=len(items)),self.assertRaises(ValueError):
                replay_panel(items,raw,plan_sha256=pin,now=now)
    def test_manifest_and_raw_zip_replayed_without_path_disclosure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pr,pin=encoded(plan());(root/'plan').write_bytes(pr)
            a=segment(86400);z=root/'SYNTHETIC.zip';z.write_bytes(a['raw'])
            m=root/'manifest.json';raw=json.dumps([dict(zip_path=str(z),zip_sha256=a['zip_sha256'])]).encode();m.write_bytes(raw)
            with patch('orrery_prospective_panel.PLAN',root/'plan'),patch('orrery_prospective_panel.PLAN_SHA256',pin):
                r=load_panel(m,sha256(raw).hexdigest())
                self.assertNotIn(str(root),json.dumps(r))
                z.write_bytes(b'corrupt')
                with self.assertRaises(ValueError):load_panel(m,sha256(raw).hexdigest())
    def test_bad_manifest_rejected_before_zip_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=Path(tmp)/'m.json'
            for value in ([],[{}],[dict(zip_path='no-such.zip',zip_sha256='0'*64,extra=True)]):
                raw=json.dumps(value).encode();m.write_bytes(raw)
                with self.assertRaises(ValueError):load_panel(m,sha256(raw).hexdigest())
            with self.assertRaisesRegex(ValueError,'hash'):load_panel(m,'0'*64)
    def test_aggregate_read_budget_is_checked_before_retaining_extra_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=Path(tmp)/'m';raw=json.dumps([dict(zip_path='a',zip_sha256='0'*64)]*3).encode();m.write_bytes(raw)
            limits=[]
            def bounded(path,limit):
                if path==m:return raw
                limits.append(limit)
                if limit==0:raise ValueError('File byte budget exceeded')
                return b'x'*(16*1024*1024)
            with patch('orrery_prospective_panel._read',side_effect=bounded):
                with self.assertRaisesRegex(ValueError,'budget'):load_panel(m,sha256(raw).hexdigest())
            self.assertEqual(limits,[16*1024*1024,16*1024*1024,0])
    def test_cli_rejects_mt5_and_missing_manifest_pin(self):
        for args in (['--prospective-manifest','x'],['--test-data','--prospective-manifest','x','--prospective-manifest-sha256','0'*64]):
            r=subprocess.run([sys.executable,'mt5_local_dashboard.py',*args],capture_output=True,timeout=10)
            self.assertEqual(r.returncode,2)
    def test_attached_snapshot_reports_input_without_claiming_full_coverage(self):
        import mt5_local_dashboard as d
        p=synthetic_panel()
        with patch.object(d,'HISTORY_SNAPSHOT',dict(status='PUBLIC_HISTORY_RESEARCH',prospective_archive=p)):
            r=d.snapshot()
        self.assertTrue(r['prospective_readiness']['data_acquired'])
        self.assertEqual(r['prospective_readiness']['prospective_candidates'],0)
        self.assertFalse(r['prospective_readiness']['complete_session_coverage_verified'])

if __name__=='__main__':unittest.main()
