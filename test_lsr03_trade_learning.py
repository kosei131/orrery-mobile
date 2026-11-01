import tempfile
from pathlib import Path
import unittest
from copy import deepcopy
from lsr03_trade_learning import start_case, review_case
from lsr02_level_observer import observe
from test_lsr02_paths import fixture


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'case'
        self.args=dict(candidate_id='candidate-1',symbol='XAUUSD',strategy_version='LSR03-research-v1',
            decision_at_msc=1000,entry_after_msc=1001,reference_price=100.05,side='BUY',
            original_plan=dict(stop=99.,target=102.),opposite_plan=dict(stop=101.,target=98.),
            level_observation=dict(observed_at=1.,levels=[dict(kind='NEAREST_SUPPORT',price=100.,
                confirmed_at=.9)],execution_allowed=False),level_tolerance=.1,market_regime='TREND',
            entry_thesis='Research support reaction with confirmed structure',
            round_trip_cost_per_unit=.1,slippage=0.,cost_source='SYNTHETIC_ASSUMPTION',data_source='SYNTHETIC')

    def start(self, **changes):
        return start_case(self.path,**dict(self.args,**changes))['decision_sha256']

    def q(self,t,bid,ask): return dict(time_msc=t,bid=bid,ask=ask)

    def review(self,pin,ticks):
        return review_case(self.path,expected_decision_sha256=pin,ticks=ticks,as_of_msc=ticks[-1]['time_msc'])

    def test_loss_does_not_imply_opposite_wins(self):
        pin=self.start()
        out=self.review(pin,[self.q(1001,100.,100.1),self.q(1100,98.9,99.),self.q(1200,101.2,101.3)])
        self.assertEqual(out['outcomes']['original']['result'],'LOSS')
        self.assertEqual(out['outcomes']['opposite']['result'],'LOSS')
        self.assertIn('BOTH_DIRECTIONS_LOST',out['observations'])
        self.assertFalse(out['automatic_rule_update']); self.assertFalse(out['execution_allowed'])

    def test_real_opposite_replay_can_win_without_being_negative_original_pnl(self):
        pin=self.start()
        out=self.review(pin,[self.q(1001,100.,100.1),self.q(1100,97.8,97.9)])
        original=out['outcomes']['original']; opposite=out['outcomes']['opposite']
        self.assertEqual((original['result'],opposite['result']),('LOSS','WIN'))
        self.assertNotAlmostEqual(original['net_price_pnl_per_unit'],-opposite['net_price_pnl_per_unit'])

    def test_entry_context_is_frozen_and_future_levels_blocked(self):
        args=deepcopy(self.args); pin=self.start(); self.args['level_observation']['levels'][0]['price']=50
        out=self.review(pin,[self.q(1001,100.,100.1),self.q(1100,102.1,102.2)])
        self.assertEqual(out['levels'][0]['price'],100.)
        other=Path(self.temp.name)/'future'
        args['level_observation']['levels'][0]['confirmed_at']=1.1
        with self.assertRaises(ValueError): start_case(other,**args)
        self.assertFalse(other.exists())

    def test_repainting_observation_clock_is_rejected(self):
        self.args['level_observation']['observed_at']=2.
        with self.assertRaises(ValueError): self.start()

    def test_gross_win_consumed_by_costs_is_loss(self):
        pin=self.start(round_trip_cost_per_unit=3.)
        out=self.review(pin,[self.q(1001,100.,100.1),self.q(1100,102.1,102.2)])
        self.assertEqual(out['outcomes']['original']['result'],'LOSS')
        self.assertIn('PRICE_GAIN_CONSUMED_BY_ASSUMED_COSTS',out['observations'])

    def test_open_is_unknown_and_later_review_keeps_same_case(self):
        pin=self.start()
        early=self.review(pin,[self.q(1001,100.,100.1),self.q(1100,100.2,100.3)])
        self.assertEqual(early['outcomes']['original']['result'],'UNKNOWN')
        self.assertIsNone(early['outcomes']['original']['net_price_pnl_per_unit'])
        late=self.review(pin,[self.q(1001,100.,100.1),self.q(1100,100.2,100.3),self.q(1200,102.1,102.2)])
        self.assertEqual(late['candidate_id'],early['candidate_id'])
        self.assertEqual(late['decision_sha256'],early['decision_sha256'])
        self.assertEqual(len(list(self.path.glob('review-*.json'))),2)

    def test_duplicate_review_not_counted_again_or_overwritten(self):
        pin=self.start(); ticks=[self.q(1001,100.,100.1)]
        self.review(pin,ticks)
        with self.assertRaises(FileExistsError): self.review(pin,ticks)
        self.assertEqual(len(list(self.path.glob('review-*.json'))),1)

    def test_future_quotes_and_wrong_pin_rejected(self):
        pin=self.start(); ticks=[self.q(1001,100.,100.1)]
        with self.assertRaises(ValueError): review_case(self.path,expected_decision_sha256=pin,
                                                      ticks=ticks,as_of_msc=1000)
        with self.assertRaises(ValueError): self.review('0'*64,ticks)

    def test_unordered_or_crossed_quotes_rejected_even_after_possible_exit(self):
        pin=self.start()
        for ticks in ([self.q(1001,100.,100.1),self.q(1200,102.1,102.2),self.q(1100,100.,100.1)],
                      [self.q(1001,100.,100.1),self.q(1200,102.1,102.2),self.q(1300,5.,4.)]):
            with self.assertRaises(ValueError): self.review(pin,ticks)

    def test_excursions_do_not_use_prices_after_original_exit(self):
        pin=self.start()
        out=self.review(pin,[self.q(1001,100.,100.1),self.q(1100,102.1,102.2),self.q(1200,200.,200.1)])
        self.assertAlmostEqual(out['outcomes']['original']['max_favorable_price_per_unit'],2.)

    def test_missing_cost_or_opposite_plan_does_not_create_context(self):
        for changes in (dict(round_trip_cost_per_unit=-1),dict(round_trip_cost_per_unit=0),
                        dict(opposite_plan=None),dict(entry_after_msc=1000)):
            with self.assertRaises(ValueError): self.start(**changes)
        self.assertFalse(self.path.exists())

    def test_unknown_fee_preserves_context_without_inventing_net_profit(self):
        pin=self.start(round_trip_cost_per_unit=None,cost_source='UNKNOWN')
        out=self.review(pin,[self.q(1001,100.,100.1),self.q(1100,102.1,102.2)])
        self.assertEqual(out['outcomes']['original']['status'],'CLOSED')
        self.assertEqual(out['outcomes']['original']['result'],'UNKNOWN')
        self.assertIsNone(out['outcomes']['original']['net_price_pnl_per_unit'])
        self.assertIn('COST_ASSUMPTION_UNKNOWN',out['observations'])

    def test_existing_level_observer_snapshot_is_accepted(self):
        h,_,_=fixture(); at=h[-1]['close_time']
        obs=observe(h,as_of=at,interval=14400,tenkan=2,kijun=2,span_b=2,shift=1)
        pin=self.start(level_observation=obs,decision_at_msc=int(at*1000),entry_after_msc=int(at*1000)+1)
        self.assertEqual(len(pin),64)


if __name__=='__main__': unittest.main()
