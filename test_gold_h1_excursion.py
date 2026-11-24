# SPDX-License-Identifier: GPL-3.0-only
from copy import deepcopy
import unittest
from unittest.mock import patch

from orrery_gold_h1_excursion import excursion, summarize, analyze


def bar(o=100,h=100.2,l=99.8,c=100):
    return dict(open=o,high=h,low=l,close=c)


def row(reason='SL_TOUCH',r=-1,exit_at=60):
    return dict(at_utc=0,side='BUY',stop_distance=1,status='RESOLVED_REFERENCE',
                exit_at=exit_at,exit_reason=reason,r=r)


class H1ExcursionTests(unittest.TestCase):
    def test_stop_minute_high_is_possible_not_guaranteed(self):
        bid={0:bar(),60:bar(h=101,l=98.5),120:bar(h=120,l=80)}
        out=excursion(row(),bid,deepcopy(bid))
        self.assertAlmostEqual(out['mfe_r_bounds'][0],.2)
        self.assertAlmostEqual(out['mfe_r_bounds'][1],1)
        self.assertEqual(out['mae_r_bounds'],[1,1])
        s=summarize([out])['thresholds']['0.5']
        self.assertEqual(s['confirmed_before_exit'],0)
        self.assertEqual(s['terminal_minute_uncertain'],1)

    def test_quotes_after_exit_cannot_change_metrics(self):
        bid={0:bar(),60:bar(h=101,l=98.5)}
        before=excursion(row(),bid,deepcopy(bid))
        bid[120]=bar(h=1000,l=1)
        self.assertEqual(before,excursion(row(),bid,deepcopy(bid)))

    def test_gap_stop_uses_only_open_and_keeps_worse_than_minus_one(self):
        bid={0:bar(),60:bar(o=98,h=150,l=90,c=100)}
        out=excursion(row('STOP_AT_OBSERVED_OPEN',-2),bid,deepcopy(bid))
        self.assertAlmostEqual(out['mfe_r_bounds'][1],.2)
        self.assertEqual(out['mae_r_bounds'],[2,2])
        self.assertAlmostEqual(out['realized_net_r'],-2.3)

    def test_target_caps_mfe_and_adverse_extreme_remains_uncertain(self):
        bid={0:bar(),60:bar(o=100.5,h=105,l=99.2)}
        out=excursion(row('TP_TOUCH',2),bid,deepcopy(bid))
        self.assertEqual(out['mfe_r_bounds'],[2,2])
        self.assertAlmostEqual(out['mae_r_bounds'][0],.2)
        self.assertAlmostEqual(out['mae_r_bounds'][1],.8)

    def test_target_floating_roundoff_cannot_create_false_uncertainty(self):
        bid={0:bar(),60:bar(h=103,l=99.9)}
        out=excursion(row('TP_TOUCH',1.99999999999999),bid,deepcopy(bid))
        s=summarize([out])['thresholds']['2']
        self.assertEqual(s['confirmed_before_exit'],1)
        self.assertEqual(s['terminal_minute_uncertain'],0)

    def test_timeout_includes_final_full_bar(self):
        bid={0:bar(),60:bar(h=101.5,l=99.4,c=101)}
        out=excursion(row('TIMEOUT_CLOSE',1,120),bid,deepcopy(bid))
        self.assertEqual(out['mfe_r_bounds'],[1.5,1.5])
        self.assertEqual(out['giveback_r_bounds'],[.5,.5])

    def test_sell_uses_ask_exit_side_and_bid_entry(self):
        bid={0:bar(l=90),60:bar(l=50)}
        ask={0:bar(o=100.2,h=100.5,l=100,c=100.4),60:bar(o=100.4,h=100.6,l=99,c=99.5)}
        r=dict(row('TIMEOUT_CLOSE',.5/1.2,120),side='SELL')
        out=excursion(r,bid,ask)
        self.assertAlmostEqual(out['mfe_r_bounds'][0],1/1.2)
        self.assertAlmostEqual(out['mae_r_bounds'][0],.6/1.2)

    def test_gap_observations_do_not_become_full_trade_values(self):
        bid={0:bar(h=100.6,l=99.5),120:bar(h=150,l=80)}
        r=dict(at_utc=0,side='BUY',stop_distance=1,status='CENSORED_AT_SIDE_GAP',last_observed_until=60)
        out=excursion(r,bid,deepcopy(bid))
        self.assertIsNone(out['mfe_r_bounds'])
        self.assertIsNone(out['realized_net_r'])
        self.assertAlmostEqual(out['observed_mfe_r_bounds'][0],.6)
        s=summarize([out])
        self.assertEqual(s['thresholds']['0.5']['incomplete_with_observed_reach'],1)
        self.assertIsNone(s['mean_mfe_r_bounds'])

    def test_ambiguous_exit_never_becomes_realized_profit(self):
        bid={0:bar(h=103,l=98)}
        r=dict(at_utc=0,side='BUY',stop_distance=1,status='AMBIGUOUS_SAME_MINUTE',exit_at=0)
        out=excursion(r,bid,deepcopy(bid))
        self.assertIsNone(out['mfe_r_bounds'])
        self.assertIsNone(out['realized_net_r'])
        self.assertEqual(out['observed_mfe_r_bounds'],[0,2])

    def test_unexpected_missing_bar_before_resolved_exit_is_rejected(self):
        bid={0:bar(),120:bar()}
        with self.assertRaises(ValueError):
            excursion(row('TIMEOUT_CLOSE',0,180),bid,deepcopy(bid))

    def test_no_entry_quote_is_not_zero_excursion(self):
        out=excursion(row(),{}, {})
        self.assertEqual(out['coverage'],'NO_ENTRY_QUOTE')
        self.assertIsNone(out['observed_mfe_r_bounds'])

    def test_threshold_categories_partition_complete_trades(self):
        bid={0:bar(),60:bar(h=101,l=98.5)}
        out=excursion(row(),bid,deepcopy(bid));s=summarize([out])
        for v in s['thresholds'].values():
            self.assertEqual(sum(v[k] for k in ('confirmed_before_exit','terminal_minute_uncertain','not_reached_before_exit')),1)

    def test_changed_original_records_are_rejected(self):
        with patch('orrery_gold_h1_excursion.signals',return_value=iter([])), \
             patch('orrery_gold_h1_excursion.replay',return_value=([],{})), \
             patch('orrery_gold_h1_excursion.replay_rising',return_value=([],{})):
            with self.assertRaises(ValueError):
                analyze({}, {}, [],0,3600,dict(BASELINE=[{}],VHF_RISING=[]))


if __name__=='__main__':
    unittest.main()
