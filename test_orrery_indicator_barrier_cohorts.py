import unittest
from orrery_indicator_barrier_cohorts import evaluate_cohorts

def case(at, status, event=None, adx=27, direction='UP'):
    return dict(decision_at=at,adx_at_decision=adx,atr_at_decision=2.1,
                ema_direction_at_decision=direction,
                outcome=dict(status=status,observed_at=event,execution_allowed=False))

class IndicatorBarrierCohortTests(unittest.TestCase):
    def test_training_boundary_outcomes_are_excluded(self):
        a=[case(300,'TP_FIRST',600),case(900,'SL_FIRST',1200),
           case(1800,'TP_FIRST',2400),case(2700,'CENSORED_HORIZON',3000)]
        r=evaluate_cohorts(a,split_at=2000,min_count=2)
        train=next(c for c in r['cohorts'] if c['partition']=='TRAIN')
        holdout=next(c for c in r['cohorts'] if c['partition']=='HOLDOUT')
        excluded=next(c for c in r['cohorts'] if c['partition']=='BOUNDARY_EXCLUDED')
        self.assertEqual(train['total'],2)
        self.assertEqual(excluded['total'],1)
        self.assertEqual(holdout['censored'],1)
        self.assertIsNone(holdout['full_cohort_win_rate'])
        self.assertFalse(r['strategy_adopted'])
        self.assertIsNone(r['net_expectancy_usd'])

    def test_ambiguous_candles_are_not_wins(self):
        r=evaluate_cohorts([case(300,'AMBIGUOUS_SAME_BAR',600)],split_at=2000)
        self.assertEqual(r['cohorts'][0]['ambiguous'],1)
        self.assertIsNone(r['cohorts'][0]['resolved_only_tp_fraction'])

    def test_invalid_adx_or_outcome_clock_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_cohorts([case(300,'TP_FIRST',600,adx=101)],split_at=2000)
        with self.assertRaises(ValueError):
            evaluate_cohorts([case(300,'TP_FIRST',300)],split_at=2000)

if __name__=='__main__':unittest.main()
