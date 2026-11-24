# SPDX-License-Identifier: GPL-3.0-only
from copy import deepcopy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from lsr03_vhf import calculate
from orrery_gold_h1_state import COST, FAMILIES, attribute, describe, features


class H1StateTests(unittest.TestCase):
    def setUp(self):
        self.at=int(datetime(2026,1,6,19,tzinfo=timezone.utc).timestamp())
        self.window=[dict(close_time=self.at-(20-i)*3600,close=100+i,high=101+i,low=99+i)
                     for i in range(21)]
        self.signal=dict(at_utc=self.at,side='BUY',stop_distance=10)

    def test_indicator_matches_existing_and_direction_is_separate(self):
        f=features(self.window,self.signal,120,120.1)
        self.assertEqual(f['vhf14_value'],calculate(self.window,period=14)['value'])
        self.assertAlmostEqual(f['efficiency20_value'],1)
        self.assertEqual(f['groups']['net20'],'ALIGNED')
        other=features(self.window,dict(self.signal,side='SELL'),120,120.1)
        self.assertEqual(other['vhf14_value'],f['vhf14_value'])
        self.assertEqual(other['groups']['net20'],'OPPOSED')
        self.assertEqual(other['groups']['ny_clock'],'13_16')

    def test_missing_quote_is_unknown_and_spread_is_not_double_counted(self):
        f=features(self.window,self.signal,120,120.1)
        self.assertAlmostEqual(f['estimated_entry_friction_r'],(.1+COST)/10.1)
        unknown=features(self.window,self.signal,120,None)
        self.assertIsNone(unknown['estimated_entry_friction_r'])
        self.assertEqual(unknown['groups']['friction_r'],'UNKNOWN')
        with self.assertRaises(ValueError):
            features(self.window,self.signal,120.1,120)

    def test_future_and_disordered_window_are_rejected(self):
        for i in (0,20):
            rows=deepcopy(self.window); rows[i]['close_time']=self.at+1
            with self.assertRaises(ValueError):
                features(rows,self.signal,120,120.1)
        rows=deepcopy(self.window); rows[3]['close_time']=rows[2]['close_time']
        with self.assertRaises(ValueError):
            features(rows,self.signal,120,120.1)

    def test_boundary_and_flat_efficiency(self):
        rows=[dict(r,close=100) for r in self.window]
        with patch('orrery_gold_h1_state.vhf',return_value=dict(status='OK',value=.4,slope='RISING')):
            f=features(rows,self.signal,100,100)
        self.assertEqual(f['groups']['vhf14'],'HIGH_RISING')
        self.assertEqual(f['groups']['net20'],'FLAT')
        self.assertEqual(f['efficiency20_value'],0)

    def test_every_family_keeps_unknown_results_and_conserves_net_r(self):
        a=dict(self.signal,status='RESOLVED_REFERENCE',r=2,initial_risk_price=10,exit_reason='TP_TOUCH')
        b=dict(self.signal,at_utc=self.at+3600,status='CENSORED_AT_SIDE_GAP')
        fa=features(self.window,self.signal,120,120.1)
        fb=dict(deepcopy(fa),at_utc=b['at_utc'],known_at_utc=b['at_utc'])
        before=deepcopy([a,b])
        out=attribute([a,b],{a['at_utc']:fa,b['at_utc']:fb})
        self.assertEqual([a,b],before)
        self.assertEqual(out['overall']['candidates'],2)
        self.assertIsNone(out['overall']['net_mean_all_candidates_r'])
        self.assertFalse(out['filtered_strategy_replayed'])
        for family,names in FAMILIES.items():
            self.assertEqual(set(out['groups'][family]),set(names))
            self.assertEqual(sum(x['candidates'] for x in out['groups'][family].values()),2)
            self.assertAlmostEqual(sum(x['net_total_resolved_r'] for x in out['groups'][family].values()),1.97)
            self.assertEqual(sum(x['resolved'] for x in out['groups'][family].values()),1)

    def test_feature_join_and_duplicate_entry_fail(self):
        row=dict(self.signal,status='CENSORED_AT_SIDE_GAP')
        with self.assertRaises(ValueError):
            attribute([row],{})
        f=features(self.window,self.signal,120,120.1)
        with self.assertRaises(ValueError):
            attribute([row,row],{self.at:f})

    def test_empty_and_all_unknown_are_not_zero_profit(self):
        empty=describe([])
        self.assertIsNone(empty['scenarios'][1]['mean_resolved_r'])
        self.assertIsNone(empty['net_mean_all_candidates_r'])
        self.assertIsNone(empty['descriptive_win_fraction_wilson95'])
        unknown=describe([dict(self.signal,status='UNKNOWN_ENTRY_HISTORY')])
        self.assertIsNone(unknown['net_mean_all_candidates_r'])
        self.assertEqual(unknown['resolved'],0)

    def test_descriptive_interval_cannot_claim_certainty(self):
        out=describe([dict(self.signal,status='RESOLVED_REFERENCE',r=2,
                           initial_risk_price=10,exit_reason='TP_TOUCH')])
        lo,hi=out['descriptive_win_fraction_wilson95']
        self.assertLess(lo,.5)
        self.assertAlmostEqual(hi,1)


if __name__=='__main__':
    unittest.main()
