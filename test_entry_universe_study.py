import random
import unittest
from orrery_entry_universe_study import confirmations
from orrery_public_xau_sequence_study import report_from_bars


def bars():
    rng=random.Random(814);m5=[];price=1000
    for i in range(9000):
        close=price+rng.uniform(-2,2)
        m5.append(dict(close_time=(i+1)*300,open=price,close=close,
                       high=max(price,close)+rng.uniform(.1,2),low=min(price,close)-rng.uniform(.1,2)))
        price=close
    m15=[]
    for i in range(0,len(m5),3):
        g=m5[i:i+3];m15.append(dict(close_time=g[-1]['close_time'],open=g[0]['open'],
            close=g[-1]['close'],high=max(b['high'] for b in g),low=min(b['low'] for b in g)))
    return m15,m5


class UniverseTests(unittest.TestCase):
    def test_vhf_subset_matches_existing_engine_exactly(self):
        m15,m5=bars();all_rows=confirmations(m15,m5)
        self.assertTrue(all_rows)
        actual=[{k:v for k,v in c.items() if k!='vhf_pass'} for c in all_rows if c['vhf_pass']]
        self.assertEqual(actual,report_from_bars(m15,m5)['confirmation_evidence'])
    def test_later_bars_do_not_change_prior_confirmations(self):
        m15,m5=bars();all_rows=confirmations(m15,m5)
        for cutoff in (900000,1800000):
            prior=confirmations([b for b in m15 if b['close_time']<=cutoff],
                                [b for b in m5 if b['close_time']<=cutoff])
            self.assertEqual(prior,[c for c in all_rows if c['confirmation_close']<=cutoff])
    def test_no_confirmation_bridges_missing_m5(self):
        m15,m5=bars();m5=[b for b in m5 if not 100000<=b['close_time']<=104000]
        for c in confirmations(m15,m5):
            self.assertFalse(c['sweep_close']<100000 and c['confirmation_close']>104000)


class SavedEvidenceTests(unittest.TestCase):
    def test_real_evidence_keeps_full_population_and_prior_vhf_counts(self):
        import json
        from pathlib import Path
        r=json.loads(Path('research_evidence/local-history-20261101/entry_universe_profitability_20261102.json').read_text())
        self.assertTrue(r['previous_vhf_all_four_models_exact_match'])
        self.assertEqual(len(r['results']),8)
        for k,v in r['results'].items():
            self.assertEqual(v['confirmation_universe'],110 if k.startswith('ALL_') else 22)
            o=v['entry_outcomes']
            self.assertEqual(v['entry_plans']+sum(v['no_entry_reasons'].values()),v['confirmation_universe'])
            self.assertEqual(o['resolved_outcomes']+o['unresolved_or_unmodeled'],v['entry_plans'])
            self.assertEqual(sum(v['stop_policy_skip_counts'].values())+v['incomplete_after_entry'],o['unresolved_or_unmodeled'])
            self.assertEqual(sum(x['resolved'] for x in v['monthly_resolved_only'].values()),o['resolved_outcomes'])
        self.assertIsNone(r['account_return_pct']);self.assertIsNone(r['net_expectancy_r'])
        self.assertFalse(r['execution_allowed']);self.assertFalse(r['out_of_sample'])

if __name__=='__main__':unittest.main()
