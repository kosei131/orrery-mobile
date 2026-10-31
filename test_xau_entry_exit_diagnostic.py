import unittest
import test_xau_structural_stops as fixture
from orrery_xau_entry_exit_diagnostic import timing

class EntryExitDiagnosticTests(unittest.TestCase):
    def simulate(self, **kwargs):
        return fixture.StructuralStopsTests().simulate_case(**kwargs)

    def test_timeout_clock_is_close_not_intraminute_guess(self):
        t=self.simulate(horizon=1)['trades_detail'][0]
        self.assertEqual(t['exit_reason'],'TIMEOUT')
        self.assertEqual(t['elapsed_minutes_lower_bound'],1)
        self.assertEqual(t['exit_clock'],'BAR_CLOSE')

    def test_stop_target_and_gap_reasons(self):
        cases=[([(0,100,101,90,100)],'STOP_INTRAMINUTE','MINUTE_OPEN_LOWER_BOUND'),
               ([(0,100,120,99,100)],'TP_INTRAMINUTE','MINUTE_OPEN_LOWER_BOUND'),
               ([(0,100,101,99,100),(1,80,81,79,80)],'STOP_AT_OPEN','OBSERVED_MINUTE_OPEN')]
        for rows,reason,clock in cases:
            with self.subTest(reason=reason):
                t=self.simulate(rows=rows,horizon=len(rows))['trades_detail'][0]
                self.assertEqual(t['exit_reason'],reason)
                self.assertEqual(t['exit_clock'],clock)

    def test_extending_horizon_cannot_change_entry_or_stop(self):
        rows=[(0,100,101,99,100),(1,100,120,99,110)]
        short=self.simulate(rows=rows,horizon=1)['trades_detail'][0]
        long=self.simulate(rows=rows,horizon=2)['trades_detail'][0]
        self.assertEqual(short['exit_reason'],'TIMEOUT')
        self.assertEqual(long['exit_reason'],'TP_INTRAMINUTE')
        for key in ('entry_assumed','stop_assumed','target_assumed','initial_stop_distance'):
            self.assertEqual(short[key],long[key])

    def test_timing_and_drift_buy_sell_symmetry(self):
        c=fixture.candidate();sell=fixture.candidate('SELL')
        q={fixture.T+60:100,fixture.T+120:102}
        buy,s=timing([c,sell],q)
        self.assertEqual(buy['confirmation_to_entry_minutes'],1)
        self.assertEqual(buy['sweep_to_entry_minutes'],2)
        self.assertEqual(buy['directional_quote_drift_since_confirmation'],2)
        self.assertEqual(s['directional_quote_drift_since_confirmation'],-2)

    def test_future_quotes_outcomes_do_not_change_timing(self):
        c=fixture.candidate();q={fixture.T+60:100,fixture.T+120:102}
        a=timing([c],q)
        self.assertEqual(a,timing([dict(c,r=999)],{**q,fixture.T+999:1}))
        self.assertIsNone(timing([c],{})[0]['directional_quote_drift_since_confirmation'])

    def test_invalid_and_duplicate_timing_rejected(self):
        for cs in ([fixture.candidate(),fixture.candidate()],
                   [dict(fixture.candidate(),confirmation_close=fixture.T+120)]):
            with self.subTest(cs=cs),self.assertRaises(ValueError):timing(cs,{})

if __name__=='__main__':unittest.main()
