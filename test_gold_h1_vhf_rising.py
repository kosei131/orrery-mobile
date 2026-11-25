# SPDX-License-Identifier: GPL-3.0-only
import unittest
from unittest.mock import patch

from orrery_gold_h1_vhf_rising import replay_rising


class RisingReplayTests(unittest.TestCase):
    def test_filter_replays_all_raw_candidates_before_occupation(self):
        # First baseline entry occupies the second clock. Removing it must allow
        # the second raw signal to be considered by the actual replay engine.
        raw=[dict(at_utc=60,side='BUY',stop_distance=1),dict(at_utc=120,side='BUY',stop_distance=1)]
        windows=[[dict(close_time=60)],[dict(close_time=120)]]
        def f(window,*args):
            return dict(vhf14_slope='FALLING' if window[-1]['close_time']==60 else 'RISING')
        with patch('orrery_gold_h1_vhf_rising.signals',return_value=iter(raw)), \
             patch('orrery_gold_h1_vhf_rising.chains',return_value=iter(windows)), \
             patch('orrery_gold_h1_vhf_rising.features',side_effect=f), \
             patch('orrery_gold_h1_vhf_rising.replay',return_value=([],{})) as actual:
            _,counts=replay_rising([],{}, {},1000)
        self.assertEqual(actual.call_args.args[0],[raw[1]])
        self.assertEqual(counts['raw_signals'],2)
        self.assertEqual(counts['passing_signals'],1)

    def test_flat_vhf_is_excluded_and_quote_missing_does_not_exclude_rising(self):
        raw=[dict(at_utc=60,side='BUY',stop_distance=1),dict(at_utc=120,side='BUY',stop_distance=1)]
        def f(window,*args):
            self.assertEqual(args[-2:],(None,None))
            return dict(vhf14_slope='FLAT' if window[-1]['close_time']==60 else 'RISING')
        with patch('orrery_gold_h1_vhf_rising.signals',return_value=iter(raw)), \
             patch('orrery_gold_h1_vhf_rising.chains',return_value=iter([[dict(close_time=60)],[dict(close_time=120)]])), \
             patch('orrery_gold_h1_vhf_rising.features',side_effect=f):
            rows,counts=replay_rising([],{}, {},1000)
        self.assertEqual(counts['excluded_by_vhf'],1)
        self.assertEqual(rows[0]['status'],'UNKNOWN_ENTRY_HISTORY')


if __name__=='__main__':
    unittest.main()
