# SPDX-License-Identifier: GPL-3.0-only
from copy import deepcopy
from datetime import datetime,timezone
import unittest

from orrery_gold_h1_initial_motion import evaluate_motion,replay_motion
from orrery_gold_h1_half_target import replay_target


class InitialMotionTests(unittest.TestCase):
    def setUp(self):
        self.at=int(datetime(2026,1,6,19,tzinfo=timezone.utc).timestamp())
        self.bid={self.at+i*60:dict(open=100,high=100.1,low=99.9,close=100) for i in range(180)}
        self.ask=deepcopy(self.bid)
        self.signal=dict(at_utc=self.at,side='BUY',stop_distance=1)

    def test_weak_decision_uses_completed_close_and_next_open_fill(self):
        check=self.at+900
        self.bid[check].update(open=99.7,high=105,low=97)
        out=evaluate_motion(self.signal,self.bid,self.ask,60)
        self.assertEqual(out['exit_reason'],'WEAK_15M_NEXT_OPEN')
        self.assertAlmostEqual(out['r'],-.3)
        self.assertAlmostEqual(out['checkpoint_net_r'],-.3)
        self.assertEqual(out['checkpoint_known_at'],check)
        before=deepcopy(out)
        self.bid[check].update(high=500,low=1,close=499)
        self.assertEqual(out,evaluate_motion(self.signal,self.bid,self.ask,60))

    def test_precheck_stop_is_kept_before_later_recovery(self):
        self.bid[self.at+300]['low']=98.9
        self.bid[self.at+1200]['high']=110
        out=evaluate_motion(self.signal,self.bid,self.ask,60)
        self.assertEqual(out['exit_reason'],'SL_TOUCH')
        self.assertEqual(out['checkpoint_state'],'EXIT_OR_UNKNOWN_BEFORE_CHECK')
        self.assertNotIn('checkpoint_net_r',out)

    def test_precheck_target_is_kept(self):
        self.bid[self.at+300]['high']=102.1
        out=evaluate_motion(self.signal,self.bid,self.ask,60)
        self.assertEqual(out['exit_reason'],'TP_TOUCH')
        self.assertAlmostEqual(out['r'],2)

    def test_precheck_gap_cannot_be_treated_as_strong_or_weak(self):
        del self.ask[self.at+300]
        out=evaluate_motion(self.signal,self.bid,self.ask,60)
        self.assertEqual(out['status'],'CENSORED_AT_SIDE_GAP')
        self.assertEqual(out['last_observed_until'],self.at+300)
        self.assertNotIn('r',out)

    def test_missing_decision_execution_quote_remains_unknown(self):
        del self.ask[self.at+900]
        out=evaluate_motion(self.signal,self.bid,self.ask,60)
        self.assertEqual(out['status'],'CENSORED_AT_SIDE_GAP')
        self.assertEqual(out['checkpoint_state'],'WEAK_EXIT_REQUESTED')
        self.assertNotIn('r',out)

    def test_gap_stop_at_execution_open_has_priority_and_not_minus_one_fill(self):
        self.bid[self.at+900]['open']=97
        out=evaluate_motion(self.signal,self.bid,self.ask,60)
        self.assertEqual(out['exit_reason'],'STOP_AT_OBSERVED_OPEN')
        self.assertAlmostEqual(out['r'],-3)

    def test_target_at_execution_open_has_priority_without_filling_above_target(self):
        self.bid[self.at+900]['open']=103
        out=evaluate_motion(self.signal,self.bid,self.ask,60)
        self.assertEqual(out['exit_reason'],'TP_TOUCH')
        self.assertAlmostEqual(out['r'],2)
        self.assertEqual(out['checkpoint_state'],'WEAK_EXIT_REQUESTED')

    def test_postcheck_prices_cannot_change_strong_classification(self):
        self.bid[self.at+840]['close']=100.6
        self.bid[self.at+1200]['low']=98.9
        before=evaluate_motion(self.signal,self.bid,self.ask,60)
        self.assertEqual(before['checkpoint_state'],'STRONG_HOLD')
        self.assertEqual(before['exit_reason'],'SL_TOUCH')
        self.bid[self.at+1200].update(low=99.9,high=102.1)
        after=evaluate_motion(self.signal,self.bid,self.ask,60)
        self.assertEqual(after['exit_reason'],'TP_TOUCH')
        for field in ('checkpoint_state','checkpoint_at','checkpoint_known_at','checkpoint_net_r'):
            self.assertEqual(before[field],after[field])

    def test_gross_positive_but_below_cost_is_weak(self):
        self.bid[self.at+840]['close']=100.2
        out=evaluate_motion(self.signal,self.bid,self.ask,60)
        self.assertEqual(out['checkpoint_state'],'WEAK_EXIT_REQUESTED')

    def test_sell_uses_ask_for_checkpoint_and_execution(self):
        for r in self.ask.values():r.update(open=100.2,high=100.3,low=100.1,close=100.2)
        self.ask[self.at+900]['open']=100.3
        out=evaluate_motion(dict(self.signal,side='SELL'),self.bid,self.ask,60)
        self.assertEqual(out['exit_reason'],'WEAK_15M_NEXT_OPEN')
        self.assertAlmostEqual(out['r'],-.3/1.2)

    def test_native_boundary_before_landmark_needs_no_next_open(self):
        del self.ask[self.at+900]
        out=evaluate_motion(self.signal,self.bid,self.ask,10)
        self.assertEqual(out['exit_at'],self.at+600)
        self.assertEqual(out['checkpoint_state'],'NATIVE_BOUNDARY_BEFORE_CHECK')

    def test_same_minute_barriers_remain_ambiguous(self):
        self.bid[self.at].update(low=98.9,high=102.1)
        out=evaluate_motion(self.signal,self.bid,self.ask,60)
        self.assertEqual(out['status'],'AMBIGUOUS_SAME_MINUTE')
        self.assertIsNone(out['r'])

    def test_full_replay_can_use_new_signal_after_weak_exit(self):
        found=[self.signal,dict(self.signal,at_utc=self.at+3600)]
        old,_=replay_target(found,self.bid,self.ask,self.at+10800,2)
        rows,_=replay_motion(found,self.bid,self.ask,self.at+10800)
        self.assertEqual(len(old),1)
        self.assertEqual(len(rows),2)
        self.assertTrue(all(r['exit_reason']=='WEAK_15M_NEXT_OPEN' for r in rows))


if __name__=='__main__':unittest.main()
