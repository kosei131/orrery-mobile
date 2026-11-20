# SPDX-License-Identifier: GPL-3.0-only
import unittest

from orrery_gold_loss_attribution import attribute


class GoldLossAttributionTests(unittest.TestCase):
    def test_contributions_reconcile_and_unknown_is_preserved(self):
        rows = [
            dict(status='RESOLVED_REFERENCE', r=1.5, initial_risk_price=3, exit_reason='TP_TOUCH'),
            dict(status='RESOLVED_REFERENCE', r=-1, initial_risk_price=1, exit_reason='SL_TOUCH'),
            dict(status='CENSORED_AT_SIDE_GAP'),
        ]
        result = attribute(rows, 0, 604800)
        self.assertAlmostEqual(result['total_gross_r'], 0.5)
        self.assertAlmostEqual(result['extra_cost_r'], 0.4)
        self.assertAlmostEqual(result['total_net_r'], 0.1)
        self.assertAlmostEqual(sum(x['net_r'] for x in result['exit_contributions'].values()), 0.1)
        self.assertEqual(result['summary']['unresolved'], 1)
        self.assertEqual(result['resolved_per_calendar_week'], 2)

    def test_no_resolved_trades_has_unknown_mean(self):
        result = attribute([dict(status='AMBIGUOUS_SAME_MINUTE')], 0, 604800)
        self.assertIsNone(result['gross_mean_r'])
        self.assertIsNone(result['summary']['mean_r'])
