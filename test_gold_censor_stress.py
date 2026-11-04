import copy
import json
import unittest
from pathlib import Path
from orrery_gold_censor_stress import reconcile

ROOT=Path(__file__).resolve().parent/'research_evidence/local-history-20261101'
class CensorStressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.loads((ROOT/'entry_stability_cost_20261102.json').read_text())
        cls.scenario=json.loads((ROOT/'gold_censor_stress_20261103.json').read_text())

    def test_all_eight_models_match_real_saved_evidence(self):
        r=reconcile(self.source,self.scenario)
        self.assertEqual(r['reconciled_models'],8)
        self.assertFalse(r['adoption_allowed'])

    def test_unknown_count_not_removed(self):
        x=copy.deepcopy(self.scenario)
        x['results'][0]['unresolved']-=1
        with self.assertRaises(ValueError):reconcile(self.source,x)

    def test_changed_outcome_fails(self):
        x=copy.deepcopy(self.scenario)
        x['results'][4]['scenario_all_unknown_minus_1r_mean']=0.7
        with self.assertRaises(ValueError):reconcile(self.source,x)

    def test_changed_source_fails(self):
        x=copy.deepcopy(self.scenario)
        x['source_sha256']='0'*64
        with self.assertRaises(ValueError):reconcile(self.source,x)

    def test_false_adoption_rejected(self):
        x=copy.deepcopy(self.scenario)
        x['adoption_allowed']=True
        with self.assertRaises(ValueError):reconcile(self.source,x)

    def test_drop_model_rejected(self):
        x=copy.deepcopy(self.scenario)
        x['results'].pop()
        with self.assertRaises(ValueError):reconcile(self.source,x)

if __name__=='__main__':
    unittest.main()
