import unittest
from unittest.mock import patch
from orrery_indicator_ablation import ema_series,feature_values,classify,compare,RULES


def bars(n=120,kind='flat'):
    out=[]
    for i in range(n):
        c=100 if kind=='flat' else 100+.01*i*i if kind=='up' else 500-.01*i*i
        out.append(dict(close_time=(i+1)*300,open=c-.1,high=c+1,low=c-1,close=c))
    return out


class IndicatorAblationTests(unittest.TestCase):
    def test_ema_has_explicit_sma_seed(self):
        self.assertEqual(ema_series([1,2,3,4],3),[None,None,2,3])
    def test_future_append_cannot_change_decision_features(self):
        b=bars(150,'up');t=b[99]['close_time']
        self.assertEqual(feature_values(b,t),feature_values(b[:100],t))
        with self.assertRaises(ValueError):feature_values(b,float(t))
    def test_cloud_at_current_position_uses_26_bars_ago(self):
        b=bars(100,'up');t=b[-1]['close_time'];f=feature_values(b,t)
        changed=[dict(x) for x in b]
        for x in changed[-26:]:x.update(open=1000,high=1100,low=900,close=1000)
        g=feature_values(changed,t)
        self.assertEqual(f['current_cloud_top'],g['current_cloud_top'])
        self.assertEqual(f['current_cloud_bottom'],g['current_cloud_bottom'])
        self.assertEqual(f['cloud_calculated_at'],t-26*300)
    def test_gaps_and_missing_exact_entry_clock_do_not_get_warmup(self):
        b=bars();g=b[:50]+b[51:70]
        f=feature_values(g,g[-1]['close_time'])
        self.assertEqual(f['samples'],19)
        self.assertIsNone(f['ema50']);self.assertNotIn('current_cloud_top',f)
        self.assertIsNone(classify(f,'BUY')[RULES[0]])
        self.assertTrue(all(v is None for v in classify(feature_values(b,123),'BUY').values()))
    def test_flat_series_does_not_create_momentum_or_breakout(self):
        f=feature_values(bars(),36000);d=classify(f,'BUY')
        self.assertEqual(f['bb_upper'],100);self.assertEqual(f['bb_lower'],100)
        self.assertEqual(f['macd_histogram'],0)
        self.assertTrue(all(v is False for v in d.values()))
    def test_macd_histogram_direction_uses_causal_ema_series(self):
        up=feature_values(bars(kind='up'),36000);down=feature_values(bars(kind='down'),36000)
        self.assertGreater(up['macd_histogram'],0);self.assertLess(down['macd_histogram'],0)
        self.assertTrue(classify(up,'BUY')[RULES[2]])
        self.assertTrue(classify(down,'SELL')[RULES[2]])
    def test_donchian_excludes_latest_bar_and_atr_uses_prior_values(self):
        b=bars();b[-1].update(open=100,high=121,low=99,close=120)
        f=feature_values(b,36000);d=classify(f,'BUY')
        self.assertEqual(f['donchian_upper'],101)
        self.assertTrue(d[RULES[5]]);self.assertTrue(d[RULES[4]])
        self.assertTrue(d[RULES[6]]);self.assertAlmostEqual(f['prior20_atr_mean'],2)
    def test_pass_fail_unknown_keep_losses_and_missed_profits(self):
        rows=[dict(entry_at=300,side='BUY',status='RESOLVED_REFERENCE',r=-1),
              dict(entry_at=600,side='BUY',status='RESOLVED_REFERENCE',r=1.5),
              dict(entry_at=900,side='BUY',status='CENSORED_AT_SIDE_GAP')]
        with patch('orrery_indicator_ablation.feature_values',side_effect=[dict(adx14=28),dict(adx14=15),{}]):
            r=compare(rows,[])
        a=r['filters'][RULES[1]]
        self.assertEqual(a['groups']['PASS']['total_resolved_reference_r'],-1)
        self.assertEqual(a['missed_positive_reference_r'],1.5)
        self.assertEqual(a['avoided_negative_reference_r'],0)
        self.assertEqual(a['groups']['UNKNOWN']['status_counts'],{'CENSORED_AT_SIDE_GAP':1})
        self.assertEqual(a['evaluable_baseline']['resolved'],2)


class AblationEvidenceTests(unittest.TestCase):
    def test_full_report_hashes_baselines_and_all_three_groups_reconcile(self):
        import csv,gzip,json
        from hashlib import sha256
        from pathlib import Path
        root=Path('research_evidence/local-history-20261101')
        name='indicator_ablation_20261102'
        manifest=json.loads((root/(name+'_manifest.json')).read_text())
        zipped=(root/(name+'.json.gz')).read_bytes();raw=gzip.decompress(zipped)
        self.assertEqual(sha256(zipped).hexdigest(),manifest['gzip_sha256'])
        self.assertEqual(sha256(raw).hexdigest(),manifest['uncompressed_sha256'])
        self.assertEqual(sha256((root/(name+'.csv')).read_bytes()).hexdigest(),manifest['csv_sha256'])
        with (root/(name+'.csv')).open(newline='') as f:self.assertEqual(len(list(csv.DictReader(f))),168)
        r=json.loads(raw);self.assertEqual(len(r['models']),24);self.assertEqual(r['comparison_count'],168)
        old=json.loads((root/'entry_universe_profitability_20261102.json').read_text())
        paired=json.loads((root/'paired_archive_study_20261102.json').read_text())
        for name,m in r['models'].items():
            window,label=name.split('/');b=m['baseline']
            if window=='GETDATA_5MONTH':
                source=old['results'][label];o=source['entry_outcomes']
                self.assertEqual(b['entry_plans'],source['entry_plans'])
                self.assertEqual(b['resolved'],o['resolved_outcomes'])
                self.assertEqual(b['positive'],o['wins'])
                if o['total_r'] is not None:self.assertAlmostEqual(b['total_resolved_reference_r'],o['total_r'],delta=.00006)
            else:
                source=paired['results'][window.removeprefix('PAIRED_')]['models'][label]
                self.assertEqual(b,{k:source[k] for k in b})
            self.assertEqual(len(m['features']),b['entry_plans'])
            for f in m['features']:
                v=f['values'];self.assertEqual(v['as_of'],f['entry_at'])
                self.assertLessEqual(v['samples'],300)
                if v['latest_closed_at'] is not None:self.assertEqual(v['latest_closed_at'],f['entry_at'])
                if 'cloud_calculated_at' in v:self.assertEqual(v['cloud_calculated_at'],f['entry_at']-26*300)
            for q in m['filters'].values():
                groups=q['groups'];self.assertEqual(set(groups),{'PASS','FAIL','UNKNOWN'})
                self.assertEqual(sum(v['entry_plans'] for v in groups.values()),b['entry_plans'])
                self.assertEqual(sum(v['resolved'] for v in groups.values()),b['resolved'])
                self.assertAlmostEqual(sum(v['total_resolved_reference_r'] or 0 for v in groups.values()),b['total_resolved_reference_r'] or 0,delta=.00003)
                self.assertEqual(q['evaluable_baseline']['entry_plans'],groups['PASS']['entry_plans']+groups['FAIL']['entry_plans'])
        self.assertFalse(r['adopted']);self.assertFalse(r['execution_allowed']);self.assertFalse(r['out_of_sample'])
        self.assertIsNone(r['net_expectancy_r']);self.assertIsNone(r['account_return_pct'])


class EvidenceCheckoutTests(unittest.TestCase):
    def test_git_autocrlf_keeps_pinned_csv_and_gzip_bytes(self):
        import shutil,subprocess,tempfile
        from pathlib import Path
        if not shutil.which('git'):self.skipTest('Git executable unavailable')
        names=['research_evidence/local-history-20261101/indicator_ablation_20261102.csv',
               'research_evidence/local-history-20261101/indicator_ablation_20261102.json.gz',
               'research_evidence/local-history-20261101/indicator_ablation_20261102_manifest.json']
        with tempfile.TemporaryDirectory() as tmp:
            repo=Path(tmp)/'repo';repo.mkdir();out=Path(tmp)/'out';out.mkdir()
            (repo/'.gitattributes').write_bytes(Path('.gitattributes').read_bytes())
            for name in names:
                p=repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(Path(name).read_bytes())
            for args in (['init','-q'],['-c','core.autocrlf=true','add','--all'],
                         ['-c','core.autocrlf=true','checkout-index','--all','--prefix='+out.as_posix()+'/']):
                subprocess.run(['git',*args],cwd=repo,check=True,capture_output=True)
            for name in names:self.assertEqual((out/name).read_bytes(),Path(name).read_bytes())

if __name__=='__main__':unittest.main()
