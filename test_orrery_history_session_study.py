import copy
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_lsr02_paths import fixture
from orrery_history_session_study import paired_compare,run


class SessionStudyTests(unittest.TestCase):
    def setUp(self):
        h,m,f=fixture()
        # Retain one later H4 to cover all synthetic lower-frame bars.
        h.append(dict(h[-1],close_time=h[-1]['close_time']+14400))
        while f[-1]['close_time']<h[-1]['close_time']:
            f.append(dict(f[-1],close_time=f[-1]['close_time']+300))
        while m[-1]['close_time']<f[-1]['close_time']:
            m.append(dict(m[-1],close_time=m[-1]['close_time']+900))
        self.data={'4H':h,'15m':m,'5m':f}

    def test_identical_h4_preserves_results_and_lower_frame_pins(self):
        r=paired_compare(self.data,self.data['4H'],published_at=0)
        a,b=r['arms'].values()
        self.assertEqual(a['candidates'],b['candidates'])
        self.assertGreater(a['summaries']['LSR02']['candidates'],0)
        self.assertEqual(a['common_lower_frames_sha256'],b['common_lower_frames_sha256'])
        self.assertEqual(a['summaries'],b['summaries'])
        d=a['decision_diagnostics']
        self.assertEqual(d,b['decision_diagnostics'])
        self.assertEqual(d['m5_closes'],a['replayed_m5_bars'])
        self.assertEqual(d['candidate_transitions']['RETEST'],1)
        self.assertIsNone(r['actual_profit_usd'])
        self.assertFalse(r['independent_holdout'])
        self.assertFalse(r['execution_allowed'])

    def test_publication_rounds_up_and_excludes_prior_warmup(self):
        captured=[]
        def compare(data):
            captured.append(copy.deepcopy(data))
            return {'summaries':{},'candidates':[]}
        with patch('orrery_history_session_study.compare',side_effect=compare):
            r=paired_compare(self.data,self.data['4H'],published_at=14401)
        self.assertEqual(r['start_open_s'],28800)
        self.assertEqual(len(captured),2)
        steps={'4H':14400,'15m':900,'5m':300}
        for data in captured:
            for label,rows in data.items():
                self.assertTrue(all(b['close_time']-steps[label]>=28800 for b in rows))
        self.assertFalse(r['warmup_before_start_used'])

    def test_gap_does_not_get_filled_or_carried(self):
        h=copy.deepcopy(self.data['4H']);h.pop(3)
        r=paired_compare(self.data,h,published_at=0)
        a=r['arms']['WEEKLY_PARTIAL_UNVERIFIED']
        self.assertEqual(a['frame_coverage']['4H']['rows'],sum(
            b['close_time']<=r['end_close_s'] for b in h))
        self.assertEqual(a['frame_coverage']['4H']['gap_count'],1)
        self.assertFalse(r['candidate_state_carried_across_gaps'])

    def test_invalid_session_ohlc_and_clocks_rejected(self):
        for mutate in (lambda h:h[0].update(high=float('inf')),
                       lambda h:h[0].update(close_time=14401),
                       lambda h:h.reverse()):
            h=copy.deepcopy(self.data['4H']);mutate(h)
            with self.assertRaises(ValueError):paired_compare(self.data,h,published_at=0)
        for clock in (True,-1,float('nan'),self.data['4H'][-1]['close_time']):
            with self.subTest(clock=clock),self.assertRaises(ValueError):
                paired_compare(self.data,self.data['4H'],published_at=clock)

    def test_source_pin_failure_prevents_export(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);source=root/'source.csv';source.write_text('not input')
            with self.assertRaisesRegex(ValueError,'pin mismatch'):
                run(source,root,root/'out',expected_source_sha256='0'*64)
            self.assertFalse((root/'out').exists())

    def test_baseline_input_not_mutated(self):
        before=copy.deepcopy(self.data)
        paired_compare(self.data,self.data['4H'],published_at=0)
        self.assertEqual(before,self.data)
