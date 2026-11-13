import unittest
from copy import deepcopy
from orrery_pattern_robustness import one_position,concentration


def closed(cid,t,end,r=1.5,reason='TP_TOUCH'):
    return dict(candidate_id=cid,entry_at=t,side='BUY',status='RESOLVED_REFERENCE',exit_at=end,exit_reason=reason,r=r)


class PositionPolicyTests(unittest.TestCase):
    def test_intraminute_exit_is_not_available_until_minute_end_and_next_clock(self):
        rows=[closed('a',100,200),closed('b',220,280),closed('c',260,300),closed('d',261,400)]
        r=one_position(rows)
        self.assertEqual(r['accepted_candidate_ids'],['a','d'])
        self.assertEqual(r['decision_counts']['BLOCK_BUSY_OR_SAME_CLOCK'],2)
    def test_gap_never_creates_a_free_position_or_zero_return(self):
        rows=[dict(candidate_id='a',entry_at=100,side='BUY',status='CENSORED_AT_SIDE_GAP',last_observed_until=160),
              closed('b',200,240),closed('c',300,400),closed('d',10000,10100)]
        r=one_position(rows)
        self.assertEqual(r['accepted_candidate_ids'],['a']);self.assertTrue(r['ended_with_unknown_position'])
        self.assertEqual(r['decisions'][1]['decision'],'BLOCK_BUSY')
        self.assertEqual(r['decisions'][2]['decision'],'BLOCK_UNKNOWN_POSITION')
        self.assertIsNone(r['accepted_position_summary']['mean_resolved_reference_r'])
        self.assertIsNone(r['all_position_reference_sequence']['max_drawdown_at_exit_batches_r'])
    def test_rejected_preentry_does_not_invent_a_position(self):
        rows=[dict(candidate_id='a',entry_at=100,status='UNKNOWN_ENTRY_HISTORY',side='BUY'),closed('b',200,300)]
        r=one_position(rows)
        self.assertEqual(r['accepted_candidate_ids'],['b'])
        self.assertEqual(r['decisions'][0]['decision'],'REJECT_PREENTRY_UNKNOWN_ENTRY_HISTORY')
    def test_dual_touch_is_closed_after_minute_but_profit_stays_unknown(self):
        rows=[dict(candidate_id='a',entry_at=100,side='BUY',status='AMBIGUOUS_SAME_MINUTE',exit_at=160,r=None),
              closed('b',200,240),closed('c',221,300)]
        r=one_position(rows)
        self.assertEqual(r['accepted_candidate_ids'],['a','c'])
        self.assertEqual(r['accepted_position_summary']['resolved'],1)
        self.assertIsNone(r['all_position_reference_sequence']['max_drawdown_at_exit_batches_r'])
    def test_selection_is_independent_of_profit_and_input_order(self):
        rows=[closed('b',100,200,100),closed('a',100,200,-1),closed('c',400,500,-1)]
        a=one_position(rows);b=deepcopy(rows)
        for row in b:row['r']=-row['r']
        self.assertEqual(a['accepted_candidate_ids'],['a','c'])
        self.assertEqual(a['decisions'],one_position(list(reversed(b)))['decisions'])
    def test_unknown_status_duplicate_id_and_future_exit_mismatch_rejected(self):
        for rows in ([dict(closed('a',100,200),status='GUESS_CLOSED')],
                     [closed('a',100,200),closed('a',300,400)], [closed('a',200,100)]):
            with self.assertRaises(ValueError):one_position(rows)
    def test_open_stop_and_timeout_use_their_actual_model_confirmation_clock(self):
        for reason in ('STOP_AT_OBSERVED_OPEN','TIMEOUT_CLOSE'):
            r=one_position([closed('a',100,200,-1,reason),closed('b',200,250),closed('c',201,260)])
            self.assertEqual(r['accepted_candidate_ids'],['a','c'])
    def test_concentration_keeps_losses_and_unknowns_out_of_imputation(self):
        rows=[closed('a',100,200),closed('b',300,400),closed('c',500,600,-1),
              dict(candidate_id='d',entry_at=700,status='CENSORED_AT_SIDE_GAP')]
        r=concentration(rows)
        self.assertEqual(r['resolved_only']['resolved'],3)
        self.assertEqual(r['remove_top_positive_trades']['2']['remaining']['total_reference_r'],-1)
        self.assertFalse(r['unknown_outcomes_imputed'])


class RobustnessEvidenceTests(unittest.TestCase):
    def test_all_36_cases_preserve_candidates_and_causal_availability(self):
        import csv,gzip,json
        from hashlib import sha256
        from pathlib import Path
        root=Path('research_evidence/local-history-20261101');name='halftrend_pattern_robustness_20261102'
        manifest=json.loads((root/(name+'_manifest.json')).read_text())
        zipped=(root/(name+'.json.gz')).read_bytes();raw=gzip.decompress(zipped)
        self.assertEqual(sha256(zipped).hexdigest(),manifest['gzip_sha256'])
        self.assertEqual(sha256(raw).hexdigest(),manifest['uncompressed_sha256'])
        self.assertEqual(sha256((root/(name+'.csv')).read_bytes()).hexdigest(),manifest['csv_sha256'])
        with (root/(name+'.csv')).open(newline='') as f:self.assertEqual(len(list(csv.DictReader(f))),36)
        r=json.loads(raw);self.assertEqual(r['scenario_count'],36)
        self.assertTrue(r['baseline_twelve_models_exact_match'])
        for models in r['models'].values():
            self.assertEqual(len(models),6)
            for cases in models.values():
                self.assertEqual(set(cases),{'0.0','0.3','0.6'})
                base_ids={x['candidate_id'] for x in cases['0.0']['outcomes']}
                for c in cases.values():
                    rows=c['outcomes'];self.assertEqual({x['candidate_id'] for x in rows},base_ids)
                    self.assertEqual(len(rows),c['all_candidate_summary']['entry_plans'])
                    p=c['one_position'];self.assertEqual(sum(p['decision_counts'].values()),len(rows))
                    self.assertEqual(len(p['decisions']),len(rows))
                    accepted=p['accepted_candidate_ids'];lookup={x['candidate_id']:x for x in rows}
                    self.assertEqual(len(accepted),p['accepted_position_summary']['entry_plans'])
                    end=-1
                    for cid in accepted:
                        x=lookup[cid];self.assertIsNotNone(end);self.assertGreater(x['entry_at'],end)
                        if x['status']=='CENSORED_AT_SIDE_GAP':end=None
                        elif x['status']=='AMBIGUOUS_SAME_MINUTE':end=x['exit_at']+60
                        else:end=x['exit_at']+(60 if x['exit_reason'] in ('TP_TOUCH','SL_TOUCH') else 0)
                    self.assertEqual(p['ended_with_unknown_position'],end is None)
                    self.assertIsNone(p['account_return_pct'])
        self.assertFalse(r['adopted']);self.assertFalse(r['execution_allowed']);self.assertFalse(r['out_of_sample'])
        self.assertIsNone(r['account_return_pct']);self.assertIsNone(r['net_expectancy_r'])

if __name__=='__main__':unittest.main()
