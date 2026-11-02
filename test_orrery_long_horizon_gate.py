from datetime import datetime, timezone, timedelta
import unittest
from orrery_long_horizon_gate import assess

START=datetime(2026,1,1,tzinfo=timezone.utc)
def dt(days):return (START+timedelta(days=days)).isoformat()
def row(days, status='CLOSED_REFERENCE', value=2):
    at=int((START+timedelta(days=days)).timestamp()*1000)
    return dict(plan=dict(id=f'XAUUSD:{at}:BUY',symbol='XAUUSD',known_at_msc=at),
                reference_status=status,reference_r=value if status=='CLOSED_REFERENCE' else None,
                reference_r_exit_at=at+300000 if status=='CLOSED_REFERENCE' else None)
def report(days=200, rows=None):
    return dict(status='EXPLORATORY_WINDOW_RESET_GROSS_REFERENCE_ONLY',execution_allowed=False,
        actual_profit_usd=None,continuous_backtest_complete=False,
        common_range=dict(start_open_utc=dt(0),end_nominal_close_utc=dt(days)),
        windows=[dict(index=0,start_open_utc=dt(0),end_close_utc=dt(days))],candidates=rows or [])

class LongHorizonGateTests(unittest.TestCase):
    def test_short_history_never_passes_six_month_requirement(self):
        x=assess(report(25,[row(3),row(15)]))
        self.assertFalse(x['coverage_gate_passed'])
        self.assertFalse(x['out_of_sample_net_edge_verified'])
        self.assertIsNone(x['actual_profit_usd'])

    def test_calendar_span_with_sparse_replay_windows_fails_coverage(self):
        r=report(200,[row(10),row(180)])
        r['windows']=[
            dict(start_open_utc=dt(0),end_close_utc=dt(5)),
            dict(start_open_utc=dt(175),end_close_utc=dt(200))]
        result=assess(r)
        self.assertEqual(result['span_days'],200)
        self.assertEqual(result['observed_days'],30)
        self.assertFalse(result['coverage_gate_passed'])

    def test_plausible_weekend_gaps_are_not_automatically_authenticated(self):
        r=report(200,[row(10),row(160)])
        r['windows']=[
            dict(start_open_utc=dt(0),end_close_utc=dt(84)),
            dict(start_open_utc=dt(88),end_close_utc=dt(120)),
            dict(start_open_utc=dt(124),end_close_utc=dt(190))]
        x=assess(r)
        self.assertTrue(x['coverage_gate_passed'])
        self.assertFalse(x['session_calendar_authenticated'])
        self.assertFalse(x['six_month_backtest_complete'])

    def test_holdout_gap_blocks_even_if_training_is_complete(self):
        r=report(200,[row(10),row(180)])
        r['windows']=[
            dict(start_open_utc=dt(0),end_close_utc=dt(120)),
            dict(start_open_utc=dt(175),end_close_utc=dt(200))]
        x=assess(r)
        self.assertFalse(x['coverage_gate_passed'])
        self.assertLess(x['holdout_calendar_coverage_ratio'],0.65)

    def test_candidate_inside_unobserved_gap_is_rejected(self):
        r=report(200,[row(100)])
        r['windows']=[
            dict(start_open_utc=dt(0),end_close_utc=dt(80)),
            dict(start_open_utc=dt(120),end_close_utc=dt(200))]
        with self.assertRaisesRegex(ValueError,'outside a single observed'):
            assess(r)

    def test_resolved_exit_crossing_data_gap_is_rejected(self):
        r=report(200,[row(79)])
        r['candidates'][0]['reference_r_exit_at']=int((START+timedelta(days=121)).timestamp()*1000)
        r['windows']=[
            dict(start_open_utc=dt(0),end_close_utc=dt(80)),
            dict(start_open_utc=dt(120),end_close_utc=dt(200))]
        with self.assertRaisesRegex(ValueError,'outside a single observed'):
            assess(r)

    def test_overlapping_or_unsorted_windows_rejected(self):
        r=report(200,[row(10)])
        r['windows']=[
            dict(start_open_utc=dt(0),end_close_utc=dt(80)),
            dict(start_open_utc=dt(79),end_close_utc=dt(200))]
        with self.assertRaisesRegex(ValueError,'nonoverlapping'):
            assess(r)

    def test_long_span_with_few_trades_is_still_not_evidence(self):
        x=assess(report(200,[row(10),row(180)]))
        self.assertTrue(x['coverage_gate_passed'])
        self.assertFalse(x['sample_gate_passed'])
        self.assertIsNone(x['cohorts']['holdout']['net_expectancy_r'])

    def test_missing_and_ambiguous_outcomes_are_not_zero_losses(self):
        x=assess(report(200,[row(10),row(150,'CENSORED_AT_WINDOW_END'),
                              row(160,'AMBIGUOUS_INTRABAR')]))
        self.assertEqual(x['cohorts']['holdout']['unresolved'],2)
        self.assertFalse(x['resolution_gate_passed'])
        self.assertIsNone(x['cohorts']['holdout']['gross_mean_closed_r'])

    def test_training_exit_crossing_holdout_boundary_is_excluded(self):
        r=row(119)
        r['reference_r_exit_at']=int((START+timedelta(days=121)).timestamp()*1000)
        x=assess(report(200,[r,row(170)]))
        self.assertEqual(x['cohorts']['boundary_excluded']['candidates'],1)
        self.assertEqual(x['cohorts']['train']['candidates'],0)

    def test_duplicate_and_fabricated_solved_outcome_rejected(self):
        with self.assertRaises(ValueError):assess(report(200,[row(10),row(10)]))
        with self.assertRaises(ValueError):assess(report(200,[row(10,'CENSORED_AT_WINDOW_END',None)|{'reference_r':0}]))
        with self.assertRaises(ValueError):assess(report(200,[row(10)|{'reference_r':float('nan')}]))
        with self.assertRaises(ValueError):assess(report(200,[row(10)|{'plan':dict(row(10)['plan'],symbol='USDJPY')}]))

    def test_unresolved_candidate_with_fabricated_exit_is_rejected(self):
        candidate=row(150,'CENSORED_AT_WINDOW_END')
        candidate['reference_r_exit_at']=candidate['plan']['known_at_msc']+300000
        with self.assertRaisesRegex(ValueError,'cannot claim an exit'):
            assess(report(200,[candidate]))

    def test_no_profit_claim_even_when_many_synthetic_closed_outcomes(self):
        rows=[row(i, value=2 if i%2 else -1) for i in range(1,111)]
        rows += [row(i, value=2 if i%2 else -1) for i in range(130,190)]
        x=assess(report(200,rows))
        self.assertTrue(x['coverage_gate_passed'])
        self.assertTrue(x['sample_gate_passed'])
        self.assertFalse(x['six_month_backtest_complete'])
        self.assertFalse(x['out_of_sample_net_edge_verified'])
        self.assertFalse(x['execution_allowed'])

if __name__=='__main__':unittest.main()
