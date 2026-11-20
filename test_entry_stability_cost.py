from datetime import datetime, timezone
import json
from pathlib import Path
import unittest
from orrery_entry_stability_cost import stats, stability, CUT


def row(at,r):return dict(touch_close_utc=at,r=r)


class StabilityTests(unittest.TestCase):
    def test_empty_is_unknown_not_zero_return_or_perfect_rate(self):
        r=stability([])
        self.assertEqual(r['all_resolved']['resolved'],0)
        self.assertIsNone(r['all_resolved']['mean_reference_r'])
        self.assertIsNone(r['all_resolved']['pf_reference'])
        self.assertIsNone(r['best_month'])
        self.assertEqual(r['remove_top_positive_trades']['3']['removed_positive_trades'],0)
    def test_split_uses_entry_time_and_exact_cut_belongs_to_later(self):
        r=stability([row(CUT-60,1.5),row(CUT,-1)])
        self.assertEqual(r['before_cut']['total_reference_r'],1.5)
        self.assertEqual(r['from_cut']['total_reference_r'],-1)
        self.assertFalse(r['out_of_sample'])
    def test_remove_winners_preserves_losses_and_does_not_invent_trades(self):
        r=stability([row(CUT,1.5),row(CUT+60,1.5),row(CUT+120,-1)])
        one=r['remove_top_positive_trades']['1']['remaining']
        self.assertEqual(one['resolved'],2);self.assertEqual(one['total_reference_r'],.5)
        three=r['remove_top_positive_trades']['3']
        self.assertEqual(three['removed_positive_trades'],2)
        self.assertEqual(three['remaining']['total_reference_r'],-1)
    def test_best_month_exclusion_is_descriptive(self):
        aug=int(datetime(2026,8,1,tzinfo=timezone.utc).timestamp())
        r=stability([row(CUT,1.5),row(CUT+60,-1),row(aug,1.5)])
        self.assertEqual(r['best_month'],'2026-08')
        self.assertEqual(r['excluding_best_month']['total_reference_r'],.5)
    def test_nonfinite_reference_r_rejected(self):
        for v in (float('nan'),float('inf'),True):
            with self.assertRaises(ValueError):stats([row(CUT,v)])


class RealEvidenceTests(unittest.TestCase):
    def test_all_24_scenarios_and_unknown_metrics_are_retained(self):
        r=json.loads(Path('research_evidence/local-history-20261101/entry_stability_cost_20261102.json').read_text())
        self.assertEqual(r['scenarios'],24);self.assertEqual(len(r['models']),8)
        self.assertTrue(r['baseline_all_eight_models_exact_match'])
        for cases in r['models'].values():
            self.assertEqual(set(cases),{'0.6','1.2','2.0'})
            for c in cases.values():
                o=c['entry_outcomes'];st=c['stability']
                self.assertEqual(o['resolved_outcomes']+o['unresolved_or_unmodeled'],c['entry_plans'])
                self.assertEqual(c['entry_plans']+sum(c['no_entry_reasons'].values()),c['confirmation_universe'])
                self.assertEqual(sum(c['stop_policy_skip_counts'].values())+c['incomplete_after_entry'],o['unresolved_or_unmodeled'])
                self.assertEqual(st['before_cut']['resolved']+st['from_cut']['resolved'],o['resolved_outcomes'])
                self.assertEqual(st['all_resolved']['resolved'],o['resolved_outcomes'])
        self.assertIsNone(r['net_expectancy_r']);self.assertIsNone(r['account_return_pct'])
        self.assertFalse(r['out_of_sample']);self.assertFalse(r['execution_allowed'])

if __name__=='__main__':unittest.main()
