from copy import deepcopy
import unittest
from lsr03_filter_uncertainty import evaluate
from lsr03_matched_outcomes import audit
from test_lsr02_paths import fixture
import test_lsr03_tick_study as tick_fixture


def report(values):
    return dict(status='HYPOTHETICAL_MATCHED_CANDIDATE_RESEARCH', execution_allowed=False,
        rows=[dict(id=f'XAUUSD:{i}', group=group, status='CLOSED', net_r=r,
                   structural_at=day*86400+36000) for i,(day,group,r) in enumerate(values)])


class FilterUncertaintyTests(unittest.TestCase):
    def test_avoided_loss_and_missed_profit_use_same_net_outcomes(self):
        source = report([(1,'VHF_PASS',2.),(1,'VHF_FILTERED',-1.2),(2,'VHF_FILTERED',.4)])
        before = deepcopy(source); out = evaluate(source)
        self.assertEqual(source, before)
        obs = out['observed_closed_only']
        self.assertAlmostEqual(obs['avoided_loss_r'],1.2)
        self.assertAlmostEqual(obs['missed_profit_r'],.4)
        self.assertAlmostEqual(obs['delta_candidate_r'],.8)
        self.assertAlmostEqual(obs['filtered_total_net_r']-obs['baseline_total_net_r'],.8)
        self.assertIsNotNone(out['interval'])
        self.assertFalse(out['market_edge_verified']); self.assertFalse(out['filter_adopted'])
        self.assertFalse(out['execution_allowed'])

    def test_daily_clustering_keeps_offsetting_entries_together(self):
        source = report([(d,g,r) for d in (1,2,3) for g,r in
                         (('VHF_FILTERED',-1.),('VHF_FILTERED',1.))])
        out = evaluate(source)
        self.assertEqual(out['observed_risk_days'],3)
        self.assertEqual(out['interval']['lower'],0)
        self.assertEqual(out['interval']['upper'],0)

    def test_unknowns_are_not_zero_returns(self):
        source = report([(1,'VHF_FILTERED',-1.),(2,'VHF_PASS',2.)])
        source['rows'].append(dict(id='XAUUSD:open', group='VHF_FILTERED', status='OPEN',
                                   structural_at=3*86400+36000))
        out = evaluate(source)
        self.assertEqual(out['observed_closed_only']['delta_candidate_r'],1)
        self.assertIsNone(out['full_candidate_effect_r'])
        self.assertIsNone(out['interval'])
        self.assertEqual(out['non_closed'],1)

    def test_empty_and_single_day_do_not_fake_precision(self):
        empty = evaluate(report([]))
        self.assertIsNone(empty['interval']); self.assertIsNone(empty['full_candidate_effect_r'])
        single = evaluate(report([(1,'VHF_FILTERED',-1.)]))
        self.assertIsNone(single['interval'])
        self.assertIn('INSUFFICIENT_RISK_DAYS',single['warnings'])

    def test_observed_days_include_days_with_only_kept_candidates(self):
        out = evaluate(report([(1,'VHF_PASS',2.),(2,'VHF_FILTERED',-1.)]))
        self.assertEqual(out['observed_risk_days'],2)
        self.assertEqual(out['mean_delta_per_observed_risk_day'],.5)

    def test_hawaii_boundary_is_explicit(self):
        source = report([(1,'VHF_PASS',1.),(1,'VHF_FILTERED',-1.)])
        source['rows'][0]['structural_at'] = 86400+35999
        self.assertEqual(evaluate(source)['observed_risk_days'],2)
        self.assertEqual(evaluate(source,boundary_utc_hour=0)['observed_risk_days'],1)

    def test_seed_is_reproducible(self):
        source = report([(1,'VHF_FILTERED',-1.),(2,'VHF_FILTERED',2.),(3,'VHF_PASS',1.)])
        self.assertEqual(evaluate(source,seed=42),evaluate(source,seed=42))

    def test_duplicate_or_nonfinite_or_unknown_group_rejected(self):
        source = report([(1,'VHF_PASS',1.)])
        cases = [dict(net_r=float('nan')),dict(net_r=True),dict(group='OTHER'),
                 dict(structural_at=float('inf')),dict(status='WIN'),dict(id='OTHER:1')]
        for changes in cases:
            bad = deepcopy(source); bad['rows'][0].update(changes)
            with self.assertRaises(ValueError): evaluate(bad)
        source['rows'] *= 2
        with self.assertRaises(ValueError): evaluate(source)

    def test_mixed_symbols_and_false_realized_open_rejected(self):
        source = report([(1,'VHF_PASS',1.),(2,'VHF_FILTERED',-1.)])
        source['rows'][1]['id'] = 'USDJPY:2'
        with self.assertRaises(ValueError): evaluate(source)
        source = report([(1,'VHF_PASS',1.)]); source['rows'][0]['status'] = 'OPEN'
        with self.assertRaises(ValueError): evaluate(source)

    def test_settings_claims_and_aggregate_mismatch_rejected(self):
        source = report([(1,'VHF_FILTERED',-1.)])
        for changes in (dict(samples=1),dict(seed=True),dict(boundary_utc_hour=24)):
            with self.assertRaises(ValueError): evaluate(source,**changes)
        for changes in (dict(status='BLOCKED_GLOBAL_TICK_QUALITY'),dict(execution_allowed=True),
                        dict(market_edge_verified=True),dict(avoided_loss_r=0)):
            with self.assertRaises(ValueError): evaluate(dict(source,**changes))

    def test_resampling_budget_rejected_before_work(self):
        source = report([(day,'VHF_PASS',1.) for day in range(501)])
        with self.assertRaises(ValueError): evaluate(source,samples=10000)

    def test_existing_ohlc_matched_engine_consumed_without_changing_it(self):
        h,f,m = fixture()
        source = audit('XAUUSD',h,f,m,as_of=m[-1]['close_time'],buffer=.1)
        self.assertEqual(evaluate(source)['candidates'],len(source['rows']))

    def test_existing_bid_ask_study_decomposition_agrees(self):
        case = tick_fixture.StudyTests(); case.setUp(); self.addCleanup(case.doCleanups)
        case.build([case.q(105900001,12,12.1),case.q(106000000,8,8.1)])
        source = case.run_study(min_vhf=1)
        out = evaluate(source)
        self.assertAlmostEqual(out['observed_closed_only']['avoided_loss_r'],source['avoided_loss_r'])


if __name__ == '__main__': unittest.main()
