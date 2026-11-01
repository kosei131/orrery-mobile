import unittest
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import test_lsr03_trade_learning as fixture
from lsr03_trade_learning import start_case, review_case
from lsr03_learning_rollup import summarize
from lsr04_tick_archive import _encode


class RollupTests(unittest.TestCase):
    setUp=fixture.LearningTests.setUp
    q=fixture.LearningTests.q

    def case(self,name='case',**changes):
        root=Path(self.temp.name)/name
        args=dict(self.args,**changes)
        pin=start_case(root,**args)['decision_sha256']
        return dict(path=str(root),decision_sha256=pin,review_sha256s=[])

    def append(self,case,ticks):
        result=review_case(case['path'],expected_decision_sha256=case['decision_sha256'],
                           ticks=ticks,as_of_msc=ticks[-1]['time_msc'])
        case['review_sha256s'].append(result['review_sha256'])
        return result

    def test_latest_revision_counts_one_case(self):
        case=self.case()
        self.append(case,[self.q(1001,100.,100.1)])
        self.append(case,[self.q(1001,100.,100.1),self.q(1200,102.1,102.2)])
        out=summarize([case],as_of_msc=1200)
        self.assertEqual(out['case_versions'],1)
        self.assertEqual(out['cohorts'][0]['original']['evaluable_closed'],1)
        self.assertEqual(out['cohorts'][0]['original']['wins'],1)
        self.assertAlmostEqual(out['cohorts'][0]['original']['mean_net_r'],1.9/1.1)
        self.assertFalse(out['strategy_promoted']); self.assertFalse(out['execution_allowed'])

    def test_future_review_not_used_to_inflate_past_win_rate(self):
        case=self.case()
        self.append(case,[self.q(1001,100.,100.1)])
        self.append(case,[self.q(1001,100.,100.1),self.q(1200,102.1,102.2)])
        out=summarize([case],as_of_msc=1100)
        self.assertEqual(out['future_reviews_ignored'],1)
        self.assertIsNone(out['cohorts'][0]['original']['win_rate'])
        self.assertEqual(out['cohorts'][0]['original']['unknown'],1)

    def test_duplicate_candidate_version_is_rejected(self):
        case=self.case()
        with self.assertRaises(ValueError): summarize([case,case],as_of_msc=1200)

    def test_versions_are_separate_and_not_extra_market_trades(self):
        a=self.case('a'); b=self.case('b',strategy_version='challenger')
        for case in (a,b): self.append(case,[self.q(1001,100.,100.1),self.q(1200,102.1,102.2)])
        out=summarize([a,b],as_of_msc=1200)
        self.assertEqual(len(out['cohorts']),2)
        self.assertEqual(out['case_versions'],2)
        self.assertEqual(out['unique_symbol_candidate_pairs'],1)

    def test_instruments_are_never_pooled(self):
        a=self.case('a'); b=self.case('b',symbol='USDJPY')
        out=summarize([a,b],as_of_msc=1200)
        self.assertEqual({r['symbol'] for r in out['cohorts']},{'XAUUSD','USDJPY'})
        self.assertNotIn('total_candidate_net_r',out)

    def test_unknown_costs_and_unreviewed_cases_stay_unknown(self):
        a=self.case('a',round_trip_cost_per_unit=None,cost_source='UNKNOWN')
        b=self.case('b',candidate_id='candidate-2')
        self.append(a,[self.q(1001,100.,100.1),self.q(1200,102.1,102.2)])
        out=summarize([a,b],as_of_msc=1200)
        stats=out['cohorts'][0]['original']
        self.assertEqual(stats['candidates'],2)
        self.assertEqual(stats['unknown'],2)
        self.assertIsNone(stats['mean_net_r'])
        self.assertIsNone(stats['observed_closed_total_candidate_net_r'])
        self.assertFalse(stats['all_candidates_evaluable'])
        self.assertEqual(out['unreviewed'],1)

    def test_terminal_result_cannot_be_rewritten_in_later_review(self):
        case=self.case()
        self.append(case,[self.q(1001,100.,100.1),self.q(1200,102.1,102.2)])
        self.append(case,[self.q(1001,100.,100.1),self.q(1300,103.1,103.2)])
        with self.assertRaises(ValueError): summarize([case],as_of_msc=1300)

    def test_same_clock_conflict_and_repeated_pin_rejected(self):
        case=self.case()
        self.append(case,[self.q(1001,100.,100.1),self.q(1100,100.2,100.3)])
        self.append(case,[self.q(1001,100.,100.1),self.q(1100,100.3,100.4)])
        with self.assertRaises(ValueError): summarize([case],as_of_msc=1200)
        case['review_sha256s']=[case['review_sha256s'][0]]*2
        with self.assertRaises(ValueError): summarize([case],as_of_msc=1200)

    def test_tampered_pin_and_reanchored_approval_claim_rejected(self):
        case=self.case(); result=self.append(case,[self.q(1001,100.,100.1)])
        path=Path(case['path'])/('review-'+case['review_sha256s'][0]+'.json')
        path.write_bytes(b'{}')
        with self.assertRaises(ValueError): summarize([case],as_of_msc=1200)
        result.pop('review_sha256'); result['strategy_promoted']=True
        data=_encode(result); pin=sha256(data).hexdigest()
        (Path(case['path'])/('review-'+pin+'.json')).write_bytes(data)
        case['review_sha256s']=[pin]
        with self.assertRaises(ValueError): summarize([case],as_of_msc=1200)

    def test_line_kind_duplicate_does_not_double_count_a_case(self):
        obs=deepcopy(self.args['level_observation']); obs['levels']*=2
        case=self.case(level_observation=obs)
        self.append(case,[self.q(1001,100.,100.1),self.q(1200,102.1,102.2)])
        out=summarize([case],as_of_msc=1200)
        self.assertEqual(len(out['near_line_kind_cohorts']),1)
        self.assertEqual(out['near_line_kind_cohorts'][0]['original']['candidates'],1)

    def test_both_directions_lost_is_preserved(self):
        case=self.case()
        self.append(case,[self.q(1001,100.,100.1),self.q(1100,98.9,99.),self.q(1200,101.2,101.3)])
        out=summarize([case],as_of_msc=1200)
        self.assertEqual(out['paired_counts']['both_lost'],1)

    def test_line_kind_regime_does_not_pool_trend_and_range(self):
        a=self.case('trend'); b=self.case('range',candidate_id='range',market_regime='RANGE')
        self.append(a,[self.q(1001,100.,100.1),self.q(1100,102.1,102.2)])
        self.append(b,[self.q(1001,100.,100.1),self.q(1100,98.9,99.)])
        out=summarize([a,b],as_of_msc=1200)
        groups=out['near_line_kind_regime_cohorts']
        self.assertEqual(len(groups),2)
        by_regime={g['market_regime']:g['original'] for g in groups}
        self.assertEqual(by_regime['TREND']['wins'],1)
        self.assertEqual(by_regime['RANGE']['losses'],1)
        self.assertEqual(by_regime['TREND']['candidates'],1)
        self.assertFalse(out['strategy_promoted'])

    def test_joint_cohort_keeps_unknown_and_deduplicates_lines(self):
        obs=deepcopy(self.args['level_observation']); obs['levels']*=2
        case=self.case(level_observation=obs)
        out=summarize([case],as_of_msc=1200)
        groups=out['near_line_kind_regime_cohorts']
        self.assertEqual(len(groups),1)
        self.assertEqual(groups[0]['original']['unknown'],1)
        self.assertEqual(groups[0]['original']['candidates'],1)
        self.assertIsNone(groups[0]['original']['mean_net_r'])

    def test_empty_data_not_fake_performance(self):
        out=summarize([],as_of_msc=1200)
        self.assertEqual(out['cohorts'],[])
        self.assertEqual(out['case_versions'],0)

    def test_omitting_saved_revision_from_manifest_is_rejected(self):
        case=self.case()
        self.append(case,[self.q(1001,100.,100.1)])
        case['review_sha256s']=[]
        with self.assertRaises(ValueError): summarize([case],as_of_msc=1200)

    def closed(self,name,exit_at,*,win=False,cost=.1):
        case=self.case(name,candidate_id=name,round_trip_cost_per_unit=cost)
        bid,ask=(102.1,102.2) if win else (98.9,99.)
        self.append(case,[self.q(1001,100.,100.1),self.q(exit_at,bid,ask)])
        return case

    def test_sequence_uses_exit_order_and_retains_losses(self):
        a=self.closed('loss-a',1100); b=self.closed('loss-b',1200)
        c=self.closed('win',1300,win=True)
        report=summarize([c,b,a],as_of_msc=1300)
        stats=report['cohorts'][0]['original']; seq=stats['closed_candidate_sequence']
        self.assertEqual(seq['max_consecutive_closed_losses'],2)
        self.assertAlmostEqual(seq['max_drawdown_at_exit_batches_r'],2*1.3/1.1)
        self.assertAlmostEqual(stats['mean_loss_net_r'],-1.3/1.1)
        self.assertAlmostEqual(stats['mean_win_net_r'],1.9/1.1)
        self.assertEqual(report,summarize([a,b,c],as_of_msc=1300) | {
            'source_pins_sha256':report['source_pins_sha256']})
        self.assertFalse(seq['account_drawdown_available'])
        self.assertFalse(seq['live_stop_decision_available'])

    def test_simultaneous_exits_batch_without_invented_streak(self):
        a=self.closed('loss',1100); b=self.closed('win',1100,win=True)
        stats=summarize([a,b],as_of_msc=1200)['cohorts'][0]['original']
        seq=stats['closed_candidate_sequence']
        self.assertEqual(seq['exit_batches'],1)
        self.assertEqual(seq['simultaneous_exit_batches'],1)
        self.assertIsNone(seq['max_consecutive_closed_losses'])
        self.assertEqual(seq['max_drawdown_at_exit_batches_r'],0.)

    def test_unknown_disables_complete_sequence_instead_of_zero_fill(self):
        a=self.closed('loss',1100); b=self.case('open',candidate_id='open')
        self.append(b,[self.q(1001,100.,100.1)])
        stats=summarize([a,b],as_of_msc=1200)['cohorts'][0]['original']
        seq=stats['closed_candidate_sequence']
        self.assertFalse(seq['all_candidates_evaluable'])
        self.assertIsNone(seq['max_consecutive_closed_losses'])
        self.assertIsNone(seq['max_drawdown_at_exit_batches_r'])
        self.assertEqual(stats['unknown'],1)

    def test_unknown_costs_disable_sequence_even_after_close(self):
        case=self.case(round_trip_cost_per_unit=None,cost_source='UNKNOWN')
        self.append(case,[self.q(1001,100.,100.1),self.q(1100,102.1,102.2)])
        seq=summarize([case],as_of_msc=1200)['cohorts'][0]['original']['closed_candidate_sequence']
        self.assertIsNone(seq['max_consecutive_closed_losses'])
        self.assertIsNone(seq['max_drawdown_at_exit_batches_r'])

    def test_breakeven_breaks_loss_streak(self):
        cases=[self.closed('loss-a',1100),self.closed('flat',1200,win=True,cost=2.),
               self.closed('loss-b',1300)]
        stats=summarize(cases,as_of_msc=1300)['cohorts'][0]['original']
        self.assertEqual(stats['breakeven'],1)
        self.assertEqual(stats['closed_candidate_sequence']['max_consecutive_closed_losses'],1)

    def test_future_close_does_not_enter_sequence(self):
        a=self.closed('past',1100); b=self.closed('future',1300,win=True)
        stats=summarize([a,b],as_of_msc=1200)['cohorts'][0]['original']
        self.assertEqual(stats['closed_candidate_sequence']['exit_batches'],1)
        self.assertIsNone(stats['closed_candidate_sequence']['max_drawdown_at_exit_batches_r'])

    def test_three_research_losses_do_not_issue_live_stop(self):
        cases=[self.closed(str(i),1100+i*100) for i in range(3)]
        stats=summarize(cases,as_of_msc=1300)['cohorts'][0]['original']
        self.assertEqual(stats['closed_candidate_sequence']['max_consecutive_closed_losses'],3)
        self.assertFalse(stats['closed_candidate_sequence']['live_stop_decision_available'])

    def test_all_wins_have_zero_drawdown_and_no_mean_loss(self):
        case=self.closed('win',1100,win=True)
        stats=summarize([case],as_of_msc=1200)['cohorts'][0]['original']
        self.assertEqual(stats['closed_candidate_sequence']['max_drawdown_at_exit_batches_r'],0.)
        self.assertEqual(stats['closed_candidate_sequence']['max_consecutive_closed_losses'],0)
        self.assertIsNone(stats['mean_loss_net_r']); self.assertIsNone(stats['profit_factor'])


if __name__=='__main__': unittest.main()
