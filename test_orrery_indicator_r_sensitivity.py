import unittest
from orrery_indicator_r_sensitivity import compare_regimes

def record(t,status,at,adx=27,rr=2):
    return dict(decision_at=t,adx_at_decision=adx,ema_direction_at_decision='UP',
        target_r=rr,outcome=dict(status=status,observed_at=at,execution_allowed=False))

class IndicatorRSensitivityTests(unittest.TestCase):
    def test_holdout_and_train_have_distinct_hypothetical_r(self):
        rows=[record(300,'TP_FIRST',600),record(900,'SL_FIRST',1200),
              record(2100,'SL_FIRST',2400),record(2700,'SL_FIRST',3000)]
        x=compare_regimes(rows,split_at=2000,cost_r=.2,min_resolved=2)
        train=next(v for v in x['cohorts'] if v['partition']=='TRAIN')
        test=next(v for v in x['cohorts'] if v['partition']=='HOLDOUT')
        self.assertAlmostEqual(train['full_cohort_hypothetical_cost_adjusted_mean_r'],.3)
        self.assertAlmostEqual(test['full_cohort_hypothetical_cost_adjusted_mean_r'],-1.2)
        self.assertFalse(x['holdout_edge_verified'])

    def test_unresolved_cohort_does_not_imply_profit(self):
        x=compare_regimes([record(300,'TP_FIRST',600),
                           record(900,'CENSORED_HORIZON',1200)],split_at=2000,cost_r=.1,min_resolved=1)
        train=x['cohorts'][0]
        self.assertIsNone(train['full_cohort_hypothetical_cost_adjusted_mean_r'])
        self.assertIsNone(train['verified_net_expectancy_r'])

    def test_holdout_boundary_purging_and_validation(self):
        x=compare_regimes([record(1800,'TP_FIRST',2400),
                           record(2700,'SL_FIRST',3000)],split_at=2000,cost_r=.1,min_resolved=1)
        excluded=next(v for v in x['cohorts'] if v['partition']=='EXCLUDED_BOUNDARY')
        self.assertIsNone(excluded['full_cohort_hypothetical_cost_adjusted_mean_r'])
        with self.assertRaises(ValueError):
            compare_regimes([record(300,'TP_FIRST',300)],split_at=2000,cost_r=.1)
if __name__=='__main__':unittest.main()
