import copy
import json
import unittest
from pathlib import Path
from orrery_gold_strategy_screen import evaluate, MODELS, EXPECTED_SOURCE

EVIDENCE=Path(__file__).parent/'research_evidence/local-history-20261101/entry_stability_cost_20261102.json'

class GoldStrategyScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=json.loads(EVIDENCE.read_text(encoding='utf-8'))

    def test_live_stored_evidence_all_models(self):
        r=evaluate(self.original)
        self.assertEqual(len(r['models']),8)
        self.assertEqual(set(r['models']),set(MODELS))
        self.assertFalse(r['execution_allowed'])
        self.assertFalse(r['strategy_adoption_allowed'])
        self.assertFalse(r['out_of_sample'])
        self.assertIsNone(r['net_expectancy_r'])

    def test_unknown_broker_return_not_fabricated(self):
        r=evaluate(self.original)
        self.assertIsNone(r['actual_account_return_pct'])
        for x in r['models'].values():
            self.assertFalse(x['adoption_allowed'])
            self.assertFalse(x['broker_costs_validated'])

    def test_source_mismatch_fails_closed(self):
        e=copy.deepcopy(self.original)
        e['raw_source_sha256']='0'*64
        with self.assertRaises(ValueError):evaluate(e)

    def test_claimed_oos_is_rejected(self):
        e=copy.deepcopy(self.original);e['out_of_sample']=True
        with self.assertRaises(ValueError):evaluate(e)

    def test_missing_model_is_rejected(self):
        e=copy.deepcopy(self.original);e['models'].pop(MODELS[0])
        with self.assertRaises(ValueError):evaluate(e)

    def test_missing_spread_is_rejected(self):
        e=copy.deepcopy(self.original);e['models'][MODELS[0]].pop('2.0')
        with self.assertRaises(ValueError):evaluate(e)

    def test_small_sample_cannot_pass_screen(self):
        e=copy.deepcopy(self.original)
        x=e['models'][MODELS[0]]['0.6']
        x['entry_outcomes']['resolved_outcomes']=1
        r=evaluate(e)
        self.assertFalse(r['models'][MODELS[0]]['conditions']['sufficient_resolved'])
        self.assertFalse(r['models'][MODELS[0]]['passes_exploratory_screen'])

    def test_zero_reference_mean_rejected(self):
        e=copy.deepcopy(self.original)
        e['models'][MODELS[0]]['0.6']['entry_outcomes']['mean_r']=0
        r=evaluate(e)
        self.assertFalse(r['models'][MODELS[0]]['conditions']['positive_reference_mean'])

    def test_negative_second_half_rejected(self):
        e=copy.deepcopy(self.original)
        e['models'][MODELS[0]]['0.6']['stability']['from_cut']['mean_reference_r']=-0.01
        r=evaluate(e)
        self.assertFalse(r['models'][MODELS[0]]['conditions']['positive_both_chronological_halves'])

if __name__=='__main__':
    unittest.main()
