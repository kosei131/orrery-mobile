from copy import deepcopy
import gzip,json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import orrery_pattern_entry_tradeability as study


def bar(p):return dict(open=p,high=p+.1,low=p-.1,close=p)


class TradeabilityTests(unittest.TestCase):
    def fixture(self):
        c=dict(id='a',entry_at=120,side='BUY',atr=6.,anchor_open=60,anchor_known_at=120,anchor_bid_low=95.)
        return c,{60:bar(100.),120:bar(100.)},{60:bar(100.2),120:bar(100.2)}

    def test_one_joint_gate_uses_entry_geometry_and_causal_atr(self):
        c,b,a=self.fixture();r=study.entry_features(c,'PULLBACK_RESUME_FIXED_6',b,a)
        self.assertEqual(r['group'],'PASS');self.assertEqual(r['feature_known_at'],120)
        self.assertEqual(r['initial_sl_distance'],6.)
        self.assertAlmostEqual(r['spread_to_sl'],.2/6);self.assertEqual(r['sl_to_atr100'],1.)
        self.assertEqual(study.entry_features(dict(c,atr=7.),'X_FIXED_6',b,a)['group'],'FAIL')
        a[120]=bar(101.)
        self.assertEqual(study.entry_features(c,'X_FIXED_6',b,a)['group'],'FAIL')

    def test_future_quotes_and_outcomes_cannot_change_gate(self):
        c,b,a=self.fixture();before=study.entry_features(c,'X_ANCHOR_EXTREME',b,a)
        b[999]=bar(1.);a[999]=bar(99999.)
        self.assertEqual(before,study.entry_features(c,'X_ANCHOR_EXTREME',b,a))
        self.assertEqual(before,study.entry_features(dict(c,r=999.,exit_at=999,status='WIN'),'X_ANCHOR_EXTREME',b,a))

    def test_missing_or_invalid_features_stay_unknown(self):
        c,b,a=self.fixture()
        for atr in (None,0.,float('nan')):
            self.assertEqual(study.entry_features(dict(c,atr=atr),'X_FIXED_6',b,a)['group'],'UNKNOWN')
        self.assertEqual(study.entry_features(c,'X_FIXED_6',b,{})['reason'],'ENTRY_QUOTE_MISSING')
        self.assertEqual(study.entry_features(c,'X_ANCHOR_EXTREME',{120:b[120]},a)['reason'],'ANCHOR_QUOTE_MISSING')
        self.assertEqual(study.entry_features(dict(c,anchor_bid_low=101.),'X_ANCHOR_EXTREME',b,a)['group'],'UNKNOWN')

    def test_sell_geometry_uses_original_ask_anchor(self):
        c,b,a=self.fixture();c.update(side='SELL',atr=1.)
        a[60]['high']=106.
        r=study.entry_features(c,'X_ANCHOR_EXTREME',b,a)
        self.assertEqual(r['initial_sl_distance'],6.)
        self.assertEqual(r['group'],'PASS')

    def test_future_anchor_and_crossed_quote_are_rejected(self):
        c,b,a=self.fixture()
        with self.assertRaises(ValueError):study.entry_features(dict(c,anchor_known_at=180),'X_ANCHOR_EXTREME',b,a)
        with self.assertRaises(ValueError):study.entry_features(c,'UNKNOWN_MODEL',b,a)
        a[120]=bar(99.)
        with self.assertRaises(ValueError):study.entry_features(c,'X_FIXED_6',b,a)

    def test_parent_manifest_change_is_not_silently_accepted(self):
        with TemporaryDirectory() as d:
            stem=Path(d)/'x';Path(str(stem)+'_manifest.json').write_text('{}')
            with patch.object(study,'PARENT_STEM',stem):
                with self.assertRaisesRegex(ValueError,'Stress manifest changed'):study.load_stress_parent()

    def test_candidate_duplicates_and_feature_clock_mismatch_fail(self):
        row=dict(candidate_id='a',entry_at=120)
        with self.assertRaises(ValueError):study.partition_case([row,row],{'a':dict(group='PASS',entry_at=120)})
        with self.assertRaises(ValueError):study.partition_case([row],{'a':dict(group='PASS',entry_at=180)})

    def test_all_saved_36_cases_match_parent_and_preserve_unknowns(self):
        stem=study.ROOT/'research_evidence/local-history-20261101/pattern_entry_tradeability_20261103'
        m=json.loads(Path(str(stem)+'_manifest.json').read_text());z=Path(str(stem)+'.json.gz').read_bytes()
        self.assertEqual(sha256(z).hexdigest(),m['gzip_sha256'])
        raw=gzip.decompress(z);self.assertEqual(sha256(raw).hexdigest(),m['uncompressed_sha256']);r=json.loads(raw)
        self.assertEqual(r['specification'],study.SPEC);self.assertTrue(r['all_36_baselines_exact_match'])
        self.assertFalse(r['adopted']);self.assertFalse(r['execution_allowed']);self.assertFalse(r['out_of_sample'])
        self.assertIsNone(r['net_expectancy_r']);self.assertIsNone(r['account_return_pct'])
        for name,pin in m['engine_code_sha256'].items():self.assertEqual(sha256((study.ROOT/name).read_bytes()).hexdigest(),pin)
        parent=study.load_stress_parent();count=0
        for w,models in r['models'].items():
            for name,model in models.items():
                self.assertEqual(set(model['cases']),{'0.0','0.3','0.6'})
                for f in model['features'].values():
                    if f['group']!='UNKNOWN':self.assertLessEqual(f['feature_known_at'],f['entry_at'])
                for delta,c in model['cases'].items():
                    count+=1;original=parent['results'][w][name][delta]
                    self.assertEqual(c['baseline'],original['all_candidate_summary'])
                    self.assertEqual(sum(g['entry_plans'] for g in c['groups'].values()),c['baseline']['entry_plans'])
                    self.assertEqual(c,study.partition_case(original['outcomes'],model['features']))
                    self.assertFalse(c['unknown_returns_imputed'])
                    self.assertIsNone(c['groups']['UNKNOWN']['net_expectancy_r'])
        self.assertEqual(count,36)
