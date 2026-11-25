# SPDX-License-Identifier: GPL-3.0-only
import unittest
from unittest.mock import patch

from orrery_gold_h1_q2 import compare, START, END


class H1Q2Tests(unittest.TestCase):
    def test_fixed_period_rejects_selection_after_results(self):
        with self.assertRaises(ValueError):
            compare({}, {}, [], START+60, END)

    def test_missing_outcomes_and_all_raw_candidates_are_kept(self):
        raw=[dict(at_utc=START+3600,side='BUY',stop_distance=1),
             dict(at_utc=START+7200,side='SELL',stop_distance=1)]
        rows=[dict(raw[0],status='CENSORED_AT_SIDE_GAP')]
        with patch('orrery_gold_h1_q2.aggregate_complete',return_value=[]), \
             patch('orrery_gold_h1_q2.signals',return_value=iter(raw)), \
             patch('orrery_gold_h1_q2.replay',return_value=(rows,{'OCCUPIED':1})) as base, \
             patch('orrery_gold_h1_q2.replay_rising',return_value=(rows,dict(raw_signals=2,passing_signals=1,excluded_by_vhf=1,skipped={}))):
            v=compare({}, {}, [])
        self.assertEqual(base.call_args.args[0],raw)
        self.assertEqual(v['arms']['VHF_RISING']['candidates'],1)
        self.assertIsNone(v['arms']['VHF_RISING']['net_mean_all_candidates_r'])
        self.assertEqual(v['arms']['VHF_RISING']['resolved'],0)
        self.assertEqual(sum(m['candidates'] for m in v['arms']['VHF_RISING']['by_utc_month'].values()),1)

    def test_different_candidate_universe_is_rejected(self):
        with patch('orrery_gold_h1_q2.aggregate_complete',return_value=[]), \
             patch('orrery_gold_h1_q2.signals',return_value=iter([])), \
             patch('orrery_gold_h1_q2.replay',return_value=([],{})), \
             patch('orrery_gold_h1_q2.replay_rising',return_value=([],dict(raw_signals=1))):
            with self.assertRaises(ValueError):
                compare({}, {}, [])


if __name__=='__main__':
    unittest.main()
