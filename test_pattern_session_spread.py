from copy import deepcopy
import gzip,json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import orrery_pattern_session_spread as study
from orrery_paired_archive_study import at,summary
from orrery_pattern_session_review import closure_scenario
from orrery_pattern_robustness import one_position


def bar(p):return dict(open=p,high=p+.1,low=p-.1,close=p)


class SpreadSessionTests(unittest.TestCase):
    def test_widen_both_sides_without_mutating_quotes_or_clocks(self):
        t=at('2026-09-08T12:00+00:00');b={t:bar(100.)};a={t:bar(100.2)};old=deepcopy((b,a))
        sb,sa=study.widen(b,a,.6)
        self.assertEqual((b,a),old);self.assertEqual(set(sb),set(b))
        for k in b[t]:
            self.assertAlmostEqual(sb[t][k],b[t][k]-.3)
            self.assertAlmostEqual(sa[t][k],a[t][k]+.3)
        self.assertAlmostEqual(sa[t]['open']-sb[t]['open'],.8)

    def test_reject_unknown_negative_and_nonpositive_price_scenarios(self):
        b={0:bar(100.)};a={0:bar(100.2)}
        for delta in (-.1,float('nan'),float('inf'),True,'0.3',200.):
            with self.assertRaises(ValueError):study.widen(b,a,delta)
        with self.assertRaises(ValueError):study.widen(b,{},.3)

    def test_extra_quote_difference_is_charged_on_buy_and_sell(self):
        t=at('2026-09-08T12:00+00:00');b={t:bar(100.)};a={t:bar(100.2)}
        sb,sa=study.widen(b,a,.6)
        for side in ('BUY','SELL'):
            plan=dict(first_poi_touch_close=t,side=side)
            old=closure_scenario(plan,b,a,horizon=1);new=closure_scenario(plan,sb,sa,horizon=1)
            self.assertAlmostEqual(old['r'],-.2/6);self.assertAlmostEqual(new['r'],-.8/6)
            self.assertAlmostEqual(new['initial_risk_price'],6)
            self.assertEqual(new['exit_reason'],'TIMEOUT_CLOSE')

    def test_original_structural_level_can_become_invalid_under_stress(self):
        t=at('2026-09-08T12:00+00:00');b={t:bar(100.)};a={t:bar(100.2)}
        sb,sa=study.widen(b,a,.6);plan=dict(first_poi_touch_close=t,side='BUY')
        options=dict(structural_stop=99.8,structural_known_at=t,horizon=1)
        self.assertEqual(closure_scenario(plan,b,a,**options)['status'],'RESOLVED_REFERENCE')
        self.assertEqual(closure_scenario(plan,sb,sa,**options)['status'],'STOP_INVALID_AT_ENTRY')

    def test_sell_structural_anchor_uses_original_ask_not_stressed_ask(self):
        t=at('2026-09-08T12:00+00:00')
        b={t-60:bar(100.),t:bar(100.)};a={t-60:dict(open=100.2,high=106.,low=100.1,close=100.2),t:bar(100.2)}
        c=dict(id='a',entry_at=t,side='SELL',anchor_open=t-60,anchor_known_at=t,anchor_bid_low=99.9)
        # Reach target on the following observed minute; entry and fixed anchor remain inspectable.
        b[t+60]=bar(89.);a[t+60]=bar(89.2);sb,sa=study.widen(b,a,.6)
        r=study.outcomes('SELL_ANCHOR_EXTREME',[dict(candidate_id='a')],{'a':c},b,a,sb,sa,sorted(b))[0]
        self.assertEqual(r['stop'],106.);self.assertAlmostEqual(r['entry'],99.7)
        self.assertAlmostEqual(r['initial_risk_price'],6.3)

    def test_stressed_weekend_gap_can_lose_more_than_one_r(self):
        t=at('2026-09-04T20:59+00:00');z=at('2026-09-06T22:00+00:00')
        b={t:bar(100.),z:bar(90.)};a={t:bar(100.2),z:bar(90.2)}
        sb,sa=study.widen(b,a,.6);r=closure_scenario(dict(first_poi_touch_close=t,side='BUY'),sb,sa)
        self.assertEqual(r['exit_at'],z);self.assertAlmostEqual(r['r'],-1.8)
        self.assertEqual(r['exit_reason'],'STOP_AT_OBSERVED_OPEN')

    def test_widening_does_not_fill_missing_minutes_or_holiday(self):
        for t,z in ((at('2026-09-30T22:27+00:00'),at('2026-09-30T22:29+00:00')),
                    (at('2026-09-07T20:59+00:00'),at('2026-09-07T22:00+00:00'))):
            b={t:bar(100.),z:bar(100.)};a={t:bar(100.2),z:bar(100.2)}
            sb,sa=study.widen(b,a,.3);r=closure_scenario(dict(first_poi_touch_close=t,side='BUY'),sb,sa)
            self.assertEqual(r['status'],'CENSORED_AT_SIDE_GAP');self.assertNotIn(t+60,sb)

    def test_ambiguous_bar_is_not_forced_into_a_loss_or_win(self):
        t=at('2026-09-08T12:00+00:00');b={t:dict(open=100.,high=120.,low=80.,close=100.)};a={t:dict(open=100.2,high=120.2,low=80.2,close=100.2)}
        sb,sa=study.widen(b,a,.6);r=closure_scenario(dict(first_poi_touch_close=t,side='BUY'),sb,sa)
        self.assertEqual(r['status'],'AMBIGUOUS_SAME_MINUTE');self.assertIsNone(r['r'])

    def test_changed_session_manifest_is_rejected(self):
        with TemporaryDirectory() as d:
            stem=Path(d)/'bad';Path(str(stem)+'_manifest.json').write_text('{}')
            with patch.object(study,'SESSION_STEM',stem):
                with self.assertRaisesRegex(ValueError,'Session manifest changed'):study.load_session_parent()

    def test_id_reordering_is_not_silently_paired(self):
        with self.assertRaises(ValueError):study.transitions([dict(candidate_id='a')],[dict(candidate_id='b')])

    def test_saved_all_36_cases_and_original_baseline(self):
        stem=Path(__file__).resolve().parent/'research_evidence/local-history-20261101/pattern_session_spread_20261103'
        m=json.loads(Path(str(stem)+'_manifest.json').read_text())
        z=Path(str(stem)+'.json.gz').read_bytes();self.assertEqual(sha256(z).hexdigest(),m['gzip_sha256'])
        raw=gzip.decompress(z);self.assertEqual(sha256(raw).hexdigest(),m['uncompressed_sha256'])
        r=json.loads(raw);self.assertEqual(r['scenario_count'],36)
        self.assertEqual(r['specification'],json.loads(json.dumps(study.SPEC)))
        self.assertTrue(r['baseline_twelve_individual_outcomes_and_position_policies_exact_match'])
        self.assertFalse(r['adopted']);self.assertFalse(r['execution_allowed']);self.assertFalse(r['calendar_authenticated'])
        self.assertIsNone(r['net_expectancy_r']);self.assertIsNone(r['account_return_pct'])
        for name,pin in m['engine_code_sha256'].items():
            self.assertEqual(sha256((study.ROOT/name).read_bytes()).hexdigest(),pin)
        original=study.load_parent();session=study.load_session_parent();count=0
        for window,models in r['results'].items():
            for model,cases in models.items():
                self.assertEqual(set(cases),{'0.0','0.3','0.6'})
                base=original['results'][window]['models'][model]['outcomes']
                changes={x['strict']['candidate_id']:x['conditional'] for x in session['results'][window][model]['changed_outcomes']}
                expected=[changes.get(x['candidate_id'],x) for x in base]
                self.assertEqual(cases['0.0']['outcomes'],expected)
                for case in cases.values():
                    count+=1;rows=case['outcomes']
                    self.assertEqual([x['candidate_id'] for x in rows],[x['candidate_id'] for x in base])
                    self.assertEqual(summary(rows),case['all_candidate_summary'])
                    self.assertEqual(one_position(rows),case['one_position'])
                    self.assertEqual(sum(case['status_transitions_from_zero'].values()),len(base))
                    for a,b in zip(base,rows):
                        if a['status']=='UNKNOWN_ENTRY_HISTORY':self.assertEqual(b['status'],a['status'])
                        if b['status']=='AMBIGUOUS_SAME_MINUTE':self.assertIsNone(b['r'])
        self.assertEqual(count,36)
