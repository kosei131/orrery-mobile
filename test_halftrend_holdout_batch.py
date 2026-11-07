import copy
import csv
from datetime import datetime,timezone
from hashlib import sha256
from io import BytesIO,StringIO
import json
import unittest
from unittest.mock import patch
import zipfile
from orrery_halftrend_holdout_batch import review
from orrery_halftrend_holdout import evaluate,decode_plan
from orrery_tradingview_bundle_audit import _utc
from test_halftrend_holdout import plan,encoded
from test_tradingview_bundle_audit import fixture,pack,iso


def segment(start):
    files=fixture()
    for name in ('5m.csv','15m.csv','4h.csv'):
        rows=list(csv.reader(StringIO(files[name].decode())))
        for row in rows[1:]:row[0]=str(int(row[0])+start);row[1]=iso(int(row[0]))
        stream=StringIO();csv.writer(stream).writerows(rows);files[name]=stream.getvalue().encode()
    manifest=json.loads(files['manifest.json']);manifest['cutoff_utc']=iso(start+14400)
    for row in manifest['reports']:
        for key in ('first_open_utc','last_open_utc','nominal_last_close_utc'):row[key]=iso(_utc(row[key])+start)
    files['manifest.json']=json.dumps(manifest).encode();raw=pack(files)
    return dict(raw=raw,zip_sha256=sha256(raw).hexdigest())


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.pr,self.pin=encoded(plan());self.now=datetime(1970,2,1,tzinfo=timezone.utc)
        self.a=segment(86400);self.b=segment(115200)
    def run_batch(self,items):return review(items,self.pr,plan_sha256=self.pin,now=self.now)
    def test_disjoint_segments_match_standalone_and_keep_gap_unknown(self):
        r=self.run_batch([self.b,self.a])
        for item,result in zip([self.a,self.b],r['reports']):
            self.assertEqual(result,evaluate(item['raw'],self.pr,plan_sha256=self.pin,zip_sha256=item['zip_sha256'],now=self.now))
        self.assertEqual(r['submitted_common_span_seconds'],28800)
        self.assertEqual(r['unsubmitted_common_span_gaps'][0]['elapsed_seconds'],14400)
        self.assertTrue(r['partial_period']);self.assertTrue(r['boundary_state_reset'])
        self.assertFalse(r['execution_allowed']);self.assertIsNone(r['net_expectancy_r'])
        self.assertFalse(r['reversal04_compared']);self.assertFalse(r['six_month_backtest_complete'])
    def test_same_zip_rejected(self):
        with self.assertRaisesRegex(ValueError,'Repeated ZIP'):self.run_batch([self.a,self.a])
    def test_different_zip_same_prices_overlap_rejected_before_replay(self):
        with zipfile.ZipFile(BytesIO(self.a['raw'])) as z:files={n:z.read(n) for n in z.namelist()}
        files['README.txt']=b'SAME SYNTHETIC DATA DIFFERENT ENVELOPE';raw=pack(files)
        with patch('orrery_halftrend_holdout_batch.evaluate') as engine:
            with self.assertRaisesRegex(ValueError,'Overlapping'):self.run_batch([self.a,dict(raw=raw,zip_sha256=sha256(raw).hexdigest())])
            engine.assert_not_called()
    def test_adjacent_spans_and_permutation_invariance(self):
        c=segment(100800)
        self.assertEqual(self.run_batch([self.a,c]),self.run_batch([c,self.a]))
        self.assertEqual(len(self.run_batch([self.a,c])['unsubmitted_common_span_gaps']),1)
    def test_corrupt_zip_pin_and_empty_batch_rejected(self):
        bad=copy.deepcopy(self.a);bad['zip_sha256']='0'*64
        for items in ([bad],[],[self.a]*9):
            with self.assertRaises(ValueError):self.run_batch(items)
    def test_old_period_rejected_by_existing_gate(self):
        with self.assertRaisesRegex(ValueError,'outside frozen'):self.run_batch([segment(0)])
    def test_candidate_id_repetition_rejected_even_with_disjoint_spans(self):
        def fake(raw,pr,**kwargs):
            real=evaluate(raw,pr,**kwargs);at=_utc(real['prospective_study']['common_range']['start_open_utc'])+300
            real['prospective_study']['candidates']=[dict(plan=dict(id='DUPLICATE'),entry_reference_at_s=at,halftrend_group='HALFTREND_NOT_READY')]
            return real
        with patch('orrery_halftrend_holdout_batch.evaluate',side_effect=fake):
            with self.assertRaisesRegex(ValueError,'Repeated candidate ID'):self.run_batch([self.a,self.b])
    def test_rollup_keeps_loss_and_censored_candidate_in_same_cohort(self):
        def fake(raw,pr,**kwargs):
            real=evaluate(raw,pr,**kwargs);start=_utc(real['prospective_study']['common_range']['start_open_utc'])
            loss=start==86400
            real['prospective_study']['candidates']=[dict(plan=dict(id=str(start)),entry_reference_at_s=start+300,
                reference_r=-1 if loss else None,reference_status='CLOSED_REFERENCE' if loss else 'CENSORED_AT_WINDOW_END',
                reference_r_exit_at=(start+600)*1000 if loss else None,vhf_group='VHF_PASS',halftrend_group='HALFTREND_ALIGNED')]
            return real
        with patch('orrery_halftrend_holdout_batch.evaluate',side_effect=fake):r=self.run_batch([self.a,self.b])
        summary=r['summaries']['HALFTREND_ALIGNED']
        self.assertEqual(summary['candidates'],2);self.assertEqual(summary['reference_losses'],1)
        self.assertEqual(summary['censored'],1);self.assertEqual(summary['mean_closed_gross_reference_r'],-1)
        self.assertIsNone(summary['total_all_candidates_gross_reference_r'])
        self.assertIsNone(summary['closed_reference_sequence']['max_drawdown_at_exit_batches_r'])
    def test_git_windows_autocrlf_checkout_preserves_frozen_bytes(self):
        import shutil,subprocess,tempfile
        from pathlib import Path
        from orrery_halftrend_holdout import code_pins
        if not shutil.which('git'):self.skipTest('Git executable unavailable for checkout integration')
        root=Path(__file__).resolve().parent
        name='research_evidence/local-history-20261101/halftrend_prospective_plan_20261102.json'
        raw=(root/name).read_bytes();p=json.loads(raw)
        with tempfile.TemporaryDirectory() as tmp:
            repo=Path(tmp)/'repo';repo.mkdir();out=Path(tmp)/'checkout';out.mkdir()
            (repo/'.gitattributes').write_bytes((root/'.gitattributes').read_bytes())
            for filename in [*p['code_sha256'],name]:
                target=repo/filename;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes((root/filename).read_bytes())
            for args in (['init','-q'],['-c','core.autocrlf=true','add','--all'],
                         ['-c','core.autocrlf=true','checkout-index','--all','--prefix='+out.as_posix()+'/']):
                subprocess.run(['git',*args],cwd=repo,check=True,capture_output=True)
            self.assertEqual((out/name).read_bytes(),raw)
            self.assertEqual(code_pins(out),p['code_sha256'])
    def test_published_frozen_plan_remains_usable(self):
        from pathlib import Path
        raw=Path('research_evidence/local-history-20261101/halftrend_prospective_plan_20261102.json').read_bytes()
        p=decode_plan(raw,'580ec6b919f6da6e9adb8b0973f89f3af2112000dce56ca559899bd10803c434')
        self.assertEqual(len(p['code_sha256']),40)

if __name__=='__main__':unittest.main()
