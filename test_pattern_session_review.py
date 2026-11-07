import json
import gzip
from hashlib import sha256
from pathlib import Path
import unittest
from orrery_pattern_session_review import minute_class,partition,audit_gaps,closure_scenario,SPEC
from orrery_paired_archive_study import at,evaluate_plan
from orrery_pattern_robustness import one_position


def bar(price):return dict(open=price,high=price+.1,low=price-.1,close=price)


class SessionReviewTests(unittest.TestCase):
    def test_summer_week_boundaries(self):
        for s in ('2026-09-04T21:00','2026-09-05T12:00','2026-09-06T21:59','2026-09-08T21:00'):
            self.assertEqual(minute_class(at(s+'+00:00')),'ROUTINE_CLOSED_CANDIDATE')
        for s in ('2026-09-04T20:59','2026-09-06T22:00','2026-09-08T22:00'):
            self.assertEqual(minute_class(at(s+'+00:00')),'EXPECTED_OPEN')

    def test_special_date_does_not_certify_daily_break(self):
        self.assertEqual(minute_class(at('2026-09-07T21:30+00:00')),'SPECIAL_DATE_UNRESOLVED')
        self.assertEqual(minute_class(at('2026-09-30T22:28+00:00')),'EXPECTED_OPEN')

    def test_no_extrapolation_to_winter(self):
        self.assertEqual(minute_class(at('2026-11-03T22:00+00:00')),'OUTSIDE_VERIFIED_RESEARCH_SCOPE')
        with self.assertRaises(ValueError):minute_class(61)
        with self.assertRaises(ValueError):partition(0,9*86400)

    def setup_quotes(self,day='2026-09-08',reopen_price=100.):
        t=at(day+'T20:59+00:00');z=at(day+'T22:00+00:00')
        bid={t:bar(100.),z:bar(reopen_price)}
        ask={x:{k:v+.2 for k,v in b.items()} for x,b in bid.items()}
        return dict(first_poi_touch_close=t,side='BUY'),bid,ask,z

    def test_audit_partition_and_side_mismatch(self):
        p,b,a,z=self.setup_quotes();r=audit_gaps(b,a)
        self.assertEqual(r['minute_partition'],{'ROUTINE_CLOSED_CANDIDATE':60})
        self.assertEqual(r['observed_minutes_in_routine_closed_clock'],0)
        with self.assertRaises(ValueError):audit_gaps(b,{})

    def test_reopen_stop_uses_worse_observed_open(self):
        p,b,a,z=self.setup_quotes(reopen_price=90.)
        self.assertEqual(evaluate_plan(p,b,a)['status'],'CENSORED_AT_SIDE_GAP')
        r=closure_scenario(p,b,a)
        self.assertEqual(r['exit_at'],z);self.assertLess(r['r'],-1)
        self.assertEqual(r['exit_reason'],'STOP_AT_OBSERVED_OPEN')

    def test_favorable_reopen_capped_at_target(self):
        p,b,a,z=self.setup_quotes(reopen_price=115.)
        r=closure_scenario(p,b,a)
        self.assertAlmostEqual(r['r'],1.5);self.assertTrue(r['reopen_open_target'])

    def test_timeout_in_break_uses_reopen_open(self):
        p,b,a,z=self.setup_quotes(reopen_price=101.)
        b[z]['high']=200.;b[z]['low']=1. # Not observed before the deferred open exit.
        r=closure_scenario(p,b,a,horizon=30)
        self.assertEqual(r['exit_at'],z);self.assertAlmostEqual(r['r'],.8/6)
        self.assertTrue(r['timeout_deferred_to_reopen'])
        self.assertEqual(r['exit_price_basis'],'OBSERVED_REOPEN_OPEN')

    def test_open_gap_and_special_day_remain_censored(self):
        for day in ('2026-09-07',):
            p,b,a,z=self.setup_quotes(day)
            r=closure_scenario(p,b,a)
            self.assertEqual(r['status'],'CENSORED_AT_SIDE_GAP')
            self.assertEqual(r['skipped_routine_gaps'],[])
        t=at('2026-09-30T22:27+00:00');b={t:bar(100.),t+120:bar(100.)};a={x:bar(100.2) for x in b}
        r=closure_scenario(dict(first_poi_touch_close=t,side='BUY'),b,a)
        self.assertEqual(r['gap_partition'],{'EXPECTED_OPEN':1})

    def test_source_end_is_not_a_timeout(self):
        p,b,a,z=self.setup_quotes();del b[z];del a[z]
        self.assertEqual(closure_scenario(p,b,a)['gap_class'],'SOURCE_END')

    def test_non_gap_and_preentry_results_exactly_unchanged(self):
        p,b,a,z=self.setup_quotes();b[p['first_poi_touch_close']]['low']=90.
        self.assertEqual(closure_scenario(p,b,a),evaluate_plan(p,b,a))
        opts=dict(structural_stop=99.,structural_known_at=p['first_poi_touch_close']-60)
        self.assertEqual(closure_scenario(p,b,a,**opts),evaluate_plan(p,b,a,**opts))

    def test_sell_gap_and_dual_touch(self):
        p,b,a,z=self.setup_quotes(reopen_price=115.);p['side']='SELL'
        self.assertLess(closure_scenario(p,b,a)['r'],-1)
        p,b,a,z=self.setup_quotes();b[z]['high']=115.;b[z]['low']=90.
        r=closure_scenario(p,b,a)
        self.assertEqual(r['status'],'AMBIGUOUS_SAME_MINUTE');self.assertIsNone(r['r'])

    def test_unknown_position_blocks_subsequent_entries(self):
        p,b,a,z=self.setup_quotes('2026-09-07');r=dict(closure_scenario(p,b,a),candidate_id='first')
        nxt=dict(entry_at=z,side='BUY',status='RESOLVED_REFERENCE',r=1.5,exit_at=z+60,exit_reason='TP_TOUCH',candidate_id='second')
        s=one_position([r,nxt])
        self.assertEqual(s['accepted_candidate_ids'],['first'])
        self.assertTrue(s['ended_with_unknown_position'])

    def test_weekend_is_not_filled_or_timed_out_at_an_unobserved_price(self):
        t=at('2026-09-04T20:59+00:00');z=at('2026-09-06T22:00+00:00')
        b={t:bar(100.),z:bar(101.)};a={x:bar(100.2 if x==t else 101.2) for x in b}
        r=closure_scenario(dict(first_poi_touch_close=t,side='BUY'),b,a)
        self.assertEqual(r['exit_at'],z);self.assertTrue(r['timeout_deferred_to_reopen'])
        self.assertEqual(r['skipped_routine_gaps'][0]['minutes'],2940)
        self.assertEqual(len(b),2)

    def test_saved_real_data_evidence(self):
        p=Path(__file__).resolve().parent/'research_evidence/local-history-20261101/pattern_session_review_20261103'
        raw=Path(str(p)+'.json.gz').read_bytes();m=json.loads(Path(str(p)+'_manifest.json').read_text())
        self.assertEqual(sha256(raw).hexdigest(),m['gzip_sha256'])
        raw=gzip.decompress(raw);self.assertEqual(sha256(raw).hexdigest(),m['uncompressed_sha256'])
        r=json.loads(raw)
        self.assertEqual(r['code_sha256'],sha256((p.parents[2]/'orrery_pattern_session_review.py').read_bytes()).hexdigest())
        self.assertEqual(r['specification'],SPEC);self.assertFalse(r['calendar_authenticated'])
        self.assertTrue(r['baseline_twelve_models_exact_match'])
        self.assertEqual(r['audit']['paired_minutes'],47608)
        self.assertEqual(r['audit']['minute_partition']['EXPECTED_OPEN'],1)
        self.assertEqual(r['audit']['minute_partition']['SPECIAL_DATE_UNRESOLVED'],211)
        self.assertIsNone(r['account_return_pct'])
        for ms in r['results'].values():
            for model in ms.values():
                self.assertTrue(model['all_non_gap_individual_outcomes_unchanged'])
                self.assertEqual(model['strict']['entry_plans'],model['conditional']['entry_plans'])
                for change in model['changed_outcomes']:
                    self.assertEqual(change['strict']['status'],'CENSORED_AT_SIDE_GAP')
                    for gap in change['conditional']['skipped_routine_gaps']:
                        self.assertEqual(set(partition(gap['first_missing'],gap['reopen_at'])),{'ROUTINE_CLOSED_CANDIDATE'})
