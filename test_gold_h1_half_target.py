# SPDX-License-Identifier: GPL-3.0-only
from datetime import datetime,timezone
import unittest
from orrery_gold_h1_half_target import replay_target
from orrery_gold_session_hourly import replay


class HalfTargetTests(unittest.TestCase):
    def setUp(self):
        self.at=int(datetime(2026,1,6,19,tzinfo=timezone.utc).timestamp())
        self.bid={self.at+i*60:dict(open=100,high=100.1,low=99.9,close=100) for i in range(180)}
        self.ask={t:dict(r) for t,r in self.bid.items()}
        self.found=[dict(at_utc=self.at,side='BUY',stop_distance=1),dict(at_utc=self.at+60,side='BUY',stop_distance=1)]

    def test_two_r_comparator_matches_original_and_half_releases_occupation(self):
        self.bid[self.at]['high']=100.6
        original=replay(self.found,self.bid,self.ask,self.at+10800)
        self.assertEqual(replay_target(self.found,self.bid,self.ask,self.at+10800,2),original)
        rows,_=replay_target(self.found,self.bid,self.ask,self.at+10800,.5)
        self.assertEqual(len(rows),2)
        self.assertAlmostEqual(rows[0]['r'],.5)
        self.assertEqual(rows[0]['exit_reason'],'TP_TOUCH')

    def test_same_minute_stop_and_small_target_are_unknown(self):
        self.bid[self.at].update(high=100.6,low=98.9)
        rows,_=replay_target(self.found,self.bid,self.ask,self.at+10800,.5)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['status'],'AMBIGUOUS_SAME_MINUTE')
        self.assertIsNone(rows[0]['r'])

    def test_no_new_target_search_is_allowed(self):
        with self.assertRaises(ValueError):
            replay_target([],{}, {},self.at+3600,1)


if __name__=='__main__':unittest.main()
