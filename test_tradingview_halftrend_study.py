from hashlib import sha256
import unittest
from lsr05_halftrend import calculate
from orrery_tradingview_halftrend_study import annotate,study
from test_tradingview_bundle_audit import fixture,pack


def bars(n):
    return [dict(close_time=(i+1)*300,open=100+i*.01,high=100.03+i*.01,
                 low=99.98+i*.01,close=100.02+i*.01) for i in range(n)]


def candidate(at,side='BUY'):
    return dict(plan=dict(id=str(at)+side,side=side,stop=99,target=102),
        entry_reference_at_s=at,entry_reference=100,reference_r=None,
        reference_status='CENSORED_AT_WINDOW_END',vhf_group='VHF_PASS')


class HalfTrendStudyTests(unittest.TestCase):
    def rows(self,b):return calculate(b,as_of=b[-1]['close_time'],interval=300,
                                     amplitude=2,channel_deviation=2,enabled=True)['rows']

    def test_ready_same_and_opposed_states_keep_candidate_and_exit(self):
        source=[candidate(30000),candidate(30000,'SELL')]
        result=annotate(source,self.rows(bars(100)))
        self.assertEqual([r['halftrend_group'] for r in result],['HALFTREND_ALIGNED','HALFTREND_OPPOSED'])
        for before,after in zip(source,result):
            for key,value in before.items():self.assertEqual(after[key],value)
            self.assertEqual(after['reversal04_status'],'NOT_EVALUATED_EXTERNAL_OBSERVATIONS_NOT_SUPPLIED')

    def test_insufficient_atr_history_is_unknown_not_an_opposite_signal(self):
        r=annotate([candidate(6000)],self.rows(bars(20)))[0]
        self.assertEqual(r['halftrend_group'],'HALFTREND_NOT_READY')
        self.assertIsNone(r['halftrend_state']);self.assertFalse(r['halftrend_ready'])

    def test_future_rows_do_not_rewrite_entry_annotation(self):
        b=bars(105);c=candidate(30000)
        prefix=self.rows(b[:100])
        for row in b[100:]:row.update(open=80,high=81,low=79,close=80)
        self.assertEqual(annotate([c],prefix),annotate([c],self.rows(b)))

    def test_missing_exact_clock_does_not_take_later_row(self):
        r=annotate([candidate(29999)],self.rows(bars(100)))[0]
        self.assertEqual(r['halftrend_group'],'HALFTREND_NOT_READY')
        self.assertIsNone(r['halftrend_at_s'])

    def test_duplicate_indicator_clocks_rejected(self):
        row=self.rows(bars(1))
        with self.assertRaises(ValueError):annotate([candidate(300)],row*2)

    def test_bundle_pin_and_reversal_scope_are_explicit(self):
        raw=pack(fixture())
        with self.assertRaises(ValueError):study(raw,expected_zip_sha256='0'*64)
        r=study(raw,expected_zip_sha256=sha256(raw).hexdigest())
        self.assertEqual(r['summaries']['LSR02']['candidates'],0)
        self.assertTrue(r['halftrend_cohort_compared'])
        self.assertFalse(r['reversal04_compared']);self.assertFalse(r['execution_allowed'])
        self.assertIsNone(r['actual_profit_usd'])
