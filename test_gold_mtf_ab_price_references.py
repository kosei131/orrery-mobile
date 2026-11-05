import copy
import unittest
from orrery_gold_mtf_ab_price_references import evaluate

def bar(t,op=100,hi=102,lo=98,cl=100):
    return dict(close_time=t*300,open=op,high=hi,low=lo,close=cl)

def cand(side='BUY',family='A_CONTINUATION'):
    return dict(candidate_id='one',family=family,side=side,
        known_at_utc=300,structural_stop='94' if side=='BUY' else '106',
        indicative_close='100',known_room_price='25',fill_verified=False,
        execution_allowed=False)

class PriceReferenceTests(unittest.TestCase):
    def test_buy_target(self):
        r=evaluate([bar(1),bar(2,hi=110,lo=99)], [cand()])
        row=r['records'][0]
        self.assertEqual(row['state'],'TARGET_REFERENCE')
        self.assertEqual(row['reference_r'],1.5)
        self.assertEqual(r['cohorts']['A_CONTINUATION']['resolved'],1)
        self.assertIsNone(r['net_expectancy_r'])

    def test_sell_target(self):
        c=cand('SELL','B_COUNTER_SWEEP')
        r=evaluate([bar(1),bar(2,hi=101,lo=90)], [c])
        self.assertEqual(r['records'][0]['state'],'TARGET_REFERENCE')
        self.assertEqual(r['records'][0]['reference_r'],1.5)

    def test_stop(self):
        r=evaluate([bar(1),bar(2,hi=101,lo=93)], [cand()])
        self.assertEqual(r['records'][0]['reference_r'],-1)

    def test_same_bar_both_censored(self):
        r=evaluate([bar(1),bar(2,hi=110,lo=93)], [cand()])
        self.assertEqual(r['records'][0]['state'],'AMBIGUOUS_SAME_M5')
        self.assertIsNone(r['records'][0]['reference_r'])

    def test_missing_first_m5(self):
        r=evaluate([bar(1),bar(3)], [cand()])
        self.assertEqual(r['records'][0]['state'],'CENSORED_NO_NEXT_M5')

    def test_mid_trade_gap(self):
        r=evaluate([bar(1),bar(2,hi=102,lo=98),bar(4)], [cand()])
        self.assertEqual(r['records'][0]['state'],'CENSORED_M5_GAP')

    def test_room_deteriorates_at_open(self):
        c=cand();c['known_room_price']='1'
        r=evaluate([bar(1),bar(2,op=102,hi=103,lo=101,cl=102)], [c])
        self.assertEqual(r['records'][0]['state'],'CENSORED_NO_TARGET_ROOM_AT_OPEN')

    def test_price_capped_at_known_h4_obstacle(self):
        c=cand();c['known_room_price']='5'
        r=evaluate([bar(1),bar(2,hi=105,lo=99)], [c])
        self.assertEqual(r['records'][0]['target_reference'],'105')
        self.assertAlmostEqual(r['records'][0]['reference_r'],5/6)

    def test_reject_duplicate_id(self):
        with self.assertRaises(ValueError):
            evaluate([bar(1),bar(2)],[cand(),copy.deepcopy(cand())])

    def test_signal_not_tradable(self):
        c=cand();c['execution_allowed']=True
        with self.assertRaises(ValueError):evaluate([bar(1),bar(2)],[c])

    def test_closed_bar_future_not_used(self):
        original=evaluate([bar(1),bar(2,hi=102,lo=98)],[cand()])['records'][0]
        extended=evaluate([bar(1),bar(2,hi=102,lo=98),bar(3,hi=110,lo=99)],[cand()])['records'][0]
        self.assertEqual(original['state'],'CENSORED_DATA_END')
        self.assertEqual(extended['state'],'TARGET_REFERENCE')
        self.assertEqual(original['known_at_utc'],extended['known_at_utc'])

    def test_adverse_open_after_entry(self):
        r=evaluate([bar(1),bar(2,hi=102,lo=98),bar(3,op=90,hi=91,lo=89,cl=90)],[cand()])
        self.assertEqual(r['records'][0]['state'],'ADVERSE_OPEN_REFERENCE')
        self.assertLess(r['records'][0]['reference_r'],-1)

    def test_false_win_rate_never_claimed(self):
        r=evaluate([bar(1),bar(2,hi=110,lo=99)],[cand()])
        self.assertIsNone(r['actual_win_rate_pct'])
        self.assertFalse(r['adoption_allowed'])
        self.assertFalse(r['execution_allowed'])


    def test_matched_ask_changes_entry_risk_but_bid_controls_exit(self):
        candidate = dict(cand(), known_room_price='5')
        bars = [bar(1), bar(2, hi=105, lo=99)]
        row = evaluate(bars, [candidate], buy_ask_open_by_clock={300: 101})['records'][0]
        self.assertEqual(row['entry_open_reference'], '101')
        self.assertEqual(row['target_reference'], '105')
        self.assertAlmostEqual(row['reference_r'], 4/7)
        missing = evaluate(bars, [candidate], buy_ask_open_by_clock={})['records'][0]
        self.assertEqual(missing['state'], 'CENSORED_NO_PAIRED_ASK_OPEN')
        self.assertIsNone(missing['reference_r'])
        with self.assertRaisesRegex(ValueError, 'Crossed'):
            evaluate(bars, [candidate], buy_ask_open_by_clock={300: 99})


if __name__=='__main__':
    unittest.main()
