import unittest
from orrery_forward_range_distribution import summarize

def record(t, value):
    return dict(decision_at=t,features=dict(latest_closed_at=t),
        future_label_only={'3':dict(maximum_favorable_move=value,maximum_adverse_move=value/2,closing_change=value/3)})
def study():
    return dict(status='OFFLINE_FORWARD_LABELS_NOT_PREDICTIONS',execution_allowed=False,
       interval_seconds=300,horizons=[3],
       rows=[record(t,t/300) for t in (300,600,900,1200,1500,1800,2100,2400)])

class RangeDistributionTests(unittest.TestCase):
    def test_split_excludes_overlapping_training_labels(self):
        result=summarize(study(),split_at=1800,min_train=2,min_holdout=2)
        self.assertEqual(result['train_samples'],2)
        self.assertEqual(result['excluded_at_boundary'],3)
        self.assertEqual(result['holdout_samples'],3)
        self.assertTrue(result['sample_gate_passed'])
        self.assertIsNone(result['live_future_candles'])
        self.assertFalse(result['prediction_quality_verified'])
        self.assertFalse(result['execution_allowed'])

    def test_missing_interval_and_nonfinite_label_are_rejected(self):
        s=study(); del s['interval_seconds']
        with self.assertRaises(ValueError):summarize(s,split_at=1800)
        s=study();s['rows'][0]['future_label_only']['3']['closing_change']=float('nan')
        with self.assertRaises(ValueError):summarize(s,split_at=1800)

if __name__=='__main__':unittest.main()
