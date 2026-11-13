import gzip,json
from hashlib import sha256
from pathlib import Path
import unittest
from orrery_paired_archive_study import at
from orrery_pattern_session_spread import widen
from orrery_small_tp_barrier_study import replay,metrics,wilson,load_features,load_stress_parent,ROOT,MODEL


def bar(p):return dict(open=p,high=p+.1,low=p-.1,close=p)


class SmallTPTests(unittest.TestCase):
    def fixture(self,n=1,t=None):
        t=t if t is not None else at('2026-09-08T10:00+00:00')
        return dict(first_poi_touch_close=t,side='BUY'),{t+i*60:bar(100.) for i in range(n)},{t+i*60:bar(100.2) for i in range(n)}

    def test_tp_after_120_minutes_is_not_a_timeout_in_barrier_policy(self):
        p,b,a=self.fixture(151);t=p['first_poi_touch_close'];b[t+150*60]['high']=102.
        old=replay(p,b,a,.25,'FIXED_120');new=replay(p,b,a,.25,'BARRIER_ONLY')
        self.assertEqual(old['exit_reason'],'TIMEOUT_CLOSE');self.assertEqual(old['exit_at'],t+120*60)
        self.assertEqual(new['exit_reason'],'TP_TOUCH');self.assertEqual(new['exit_at'],t+150*60)
        self.assertAlmostEqual(new['r'],.25)

    def test_a_later_recovery_does_not_erase_an_earlier_stop(self):
        p,b,a=self.fixture(151);t=p['first_poi_touch_close']
        b[t+5*60]['low']=90.;b[t+150*60]['high']=120.
        r=replay(p,b,a,.25,'BARRIER_ONLY')
        self.assertEqual(r['exit_at'],t+5*60);self.assertEqual(r['r'],-1.)

    def test_buy_ask_high_is_not_an_executable_buy_exit(self):
        p,b,a=self.fixture();t=p['first_poi_touch_close'];a[t]=dict(open=100.5,high=101.2,low=100.4,close=100.5);b[t]['high']=100.7
        r=replay(p,b,a,.05,'BARRIER_ONLY')
        self.assertEqual(r['status'],'CENSORED_AT_SIDE_GAP');self.assertLess(r['last_known_close_reference_r'],0)

    def test_sell_bid_low_is_not_an_executable_sell_exit(self):
        p,b,a=self.fixture();p['side']='SELL';t=p['first_poi_touch_close'];b[t]['low']=99.5;a[t]['low']=99.8
        r=replay(p,b,a,.05,'BARRIER_ONLY');self.assertEqual(r['status'],'CENSORED_AT_SIDE_GAP')
        a[t]['low']=99.6
        r=replay(p,b,a,.05,'BARRIER_ONLY');self.assertEqual(r['exit_reason'],'TP_TOUCH');self.assertAlmostEqual(r['r'],.05)

    def test_small_target_can_touch_in_entry_minute_without_a_one_minute_hold(self):
        p,b,a=self.fixture();t=p['first_poi_touch_close'];b[t]['high']=100.6
        r=replay(p,b,a,.05,'BARRIER_ONLY');self.assertEqual(r['exit_at'],t);self.assertAlmostEqual(r['r'],.05)

    def test_same_bar_both_barriers_remains_ambiguous(self):
        p,b,a=self.fixture();t=p['first_poi_touch_close'];b[t].update(high=101.,low=90.)
        r=replay(p,b,a,.05,'BARRIER_ONLY');self.assertEqual(r['status'],'AMBIGUOUS_SAME_MINUTE');self.assertIsNone(r['r'])
        m=metrics([r]);self.assertIsNone(m['mean_resolved_reference_r']);self.assertEqual(m['positive_rate_bounds_all_entered_pct'],[0.,100.])

    def test_source_end_does_not_close_or_count_a_losing_position_as_a_win(self):
        p,b,a=self.fixture(3);r=replay(p,b,a,1.5,'BARRIER_ONLY');m=metrics([r])
        self.assertEqual(r['gap_class'],'SOURCE_END');self.assertEqual(m['unresolved_entered'],1)
        self.assertEqual(m['positive'],0);self.assertIsNone(m['mean_resolved_reference_r'])
        self.assertLess(r['last_known_close_reference_r'],0)

    def test_open_gap_and_special_holiday_do_not_become_safe_holding_time(self):
        for t in (at('2026-09-30T22:27+00:00'),at('2026-09-07T20:59+00:00')):
            p,b,a=self.fixture(t=t);b[t+120]=bar(100.);a[t+120]=bar(100.2)
            r=replay(p,b,a,1.5,'BARRIER_ONLY');self.assertEqual(r['status'],'CENSORED_AT_SIDE_GAP')
            self.assertEqual(r['gap_class'],'UNRESOLVED')

    def test_weekend_reopen_stop_can_exceed_one_r(self):
        t=at('2026-09-04T20:59+00:00');z=at('2026-09-06T22:00+00:00')
        p,b,a=self.fixture(t=t);b[z]=bar(90.);a[z]=bar(90.2)
        r=replay(p,b,a,1.5,'BARRIER_ONLY');self.assertEqual(r['exit_at'],z);self.assertLess(r['r'],-1.)

    def test_widening_uses_execution_quotes_for_a_small_target(self):
        p,b,a=self.fixture();t=p['first_poi_touch_close'];b[t]['high']=100.6
        self.assertEqual(replay(p,b,a,.05,'BARRIER_ONLY')['status'],'RESOLVED_REFERENCE')
        sb,sa=widen(b,a,.6)
        self.assertEqual(replay(p,sb,sa,.05,'BARRIER_ONLY')['status'],'CENSORED_AT_SIDE_GAP')

    def test_ninety_five_percent_wins_can_have_negative_expectancy(self):
        self.assertAlmostEqual(95*.05-5*1.,-.25)
        self.assertGreater(100/(1+.05),95.)
        self.assertGreater(95*.1-5*1.,0.)

    def test_wilson_is_a_sample_interval_not_a_calibrated_forecast(self):
        r=wilson(95,100);self.assertAlmostEqual(r['lower_pct'],88.825,places=3)
        self.assertFalse(r['iid_assumption_verified']);self.assertIsNone(wilson(0,0))
        self.assertGreater(wilson(100,100)['lower_pct'],95.)
        with self.assertRaises(ValueError):wilson(2,1)
        p,b,a=self.fixture()
        for tp,mode in ((0,'BARRIER_ONLY'),(.1,'UNTIL_WIN'),(float('nan'),'FIXED_120')):
            with self.assertRaises(ValueError):replay(p,b,a,tp,mode)

    def test_all_48_saved_cases_preserve_entries_and_parent_price_outcomes(self):
        stem=ROOT/'research_evidence/local-history-20261101/small_tp_barrier_20261103'
        m=json.loads(Path(str(stem)+'_manifest.json').read_text());z=Path(str(stem)+'.json.gz').read_bytes()
        self.assertEqual(sha256(z).hexdigest(),m['gzip_sha256']);raw=gzip.decompress(z)
        self.assertEqual(sha256(raw).hexdigest(),m['uncompressed_sha256']);r=json.loads(raw)
        for name,pin in m['engine_code_sha256'].items():self.assertEqual(sha256((ROOT/name).read_bytes()).hexdigest(),pin)
        self.assertEqual(r['case_count'],48);self.assertTrue(r['six_original_120_minute_1_5r_price_outcomes_match'])
        self.assertFalse(r['adopted']);self.assertFalse(r['execution_allowed']);self.assertIsNone(r['calibrated_win_probability'])
        self.assertIsNone(r['net_expectancy_r']);self.assertIsNone(r['account_return_pct'])
        parent=load_stress_parent();features=load_features();count=0
        for w,cases in r['results'].items():
            self.assertEqual(len(cases),24)
            for c in cases:
                count+=1;rows=c['outcomes'];old=parent['results'][w][MODEL][str(c['extra_spread'])]['outcomes']
                self.assertEqual([x['candidate_id'] for x in rows],[x['candidate_id'] for x in old])
                self.assertEqual(metrics(rows),c['all'])
                passed=[x for x in rows if features['models'][w][MODEL]['features'][x['candidate_id']]['group']=='PASS']
                self.assertEqual(metrics(passed),c['pass_cohort'])
                if c['exit_policy']=='BARRIER_ONLY':self.assertNotIn('TIMEOUT_CLOSE',c['all']['exit_reason_counts'])
        self.assertEqual(count,48)
