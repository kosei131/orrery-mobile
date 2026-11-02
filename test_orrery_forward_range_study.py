import unittest
from orrery_forward_range_study import study

def bars(n=130):
    return [dict(close_time=(i+1)*300,open=2000+i,high=2002+i,
                 low=1999+i,close=2001+i) for i in range(n)]

class ForwardRangeTests(unittest.TestCase):
    def test_only_future_outcome_labels_not_predicted_candles(self):
        r=study(bars())
        self.assertGreater(r['samples'],0)
        self.assertEqual(r['horizons'],[3,6,12])
        self.assertIsNone(r['forecast_candles'])
        self.assertFalse(r['calibrated_probabilities'])
        self.assertFalse(r['execution_allowed'])
        self.assertGreater(r['rows'][0]['future_label_only']['3']['maximum_favorable_move'],0)

    def test_future_change_does_not_change_prior_features(self):
        x=bars(); y=bars()
        y[-1]['high']+=500;y[-1]['close']+=100
        a=study(x,stride=1);b=study(y,stride=1)
        self.assertEqual(a['rows'][0]['features'],b['rows'][0]['features'])
        self.assertEqual(a['rows'][0]['decision_at'],b['rows'][0]['decision_at'])

    def test_gap_is_rejected(self):
        x=bars();x[50]['close_time']+=1
        with self.assertRaises(ValueError):study(x)

if __name__=='__main__':unittest.main()
