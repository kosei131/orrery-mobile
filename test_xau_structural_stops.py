import csv,json,tempfile,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from orrery_xau_hypothetical_pnl import simulate
from orrery_xau_structural_stop_comparison import stop_specs

BASE=datetime(2026,6,1,tzinfo=timezone.utc)
T=int(BASE.timestamp())
def candidate(side='BUY'):
    return dict(sweep_close=T,confirmation_close=T+60,first_poi_touch_close=T+120,side=side)
def m15():
    return [dict(close_time=T,low=90,high=110)]
def preentry():
    return [dict(at=T,low=99,high=101),dict(at=T+60,low=99,high=101)]

class StructuralStopsTests(unittest.TestCase):
    def simulate_case(self, side='BUY', spec=None, rows=None, horizon=2):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);src=root/'m1.csv';events=root/'events.json'
            if rows is None:rows=[(0,100,101,99,100),(1,100,102,99,101)]
            with src.open('w',newline='',encoding='utf-8') as f:
                w=csv.writer(f);w.writerow(['timestamp_utc','bid_open','bid_high','bid_low','bid_close'])
                for minute,o,h,l,c in rows:
                    w.writerow([(BASE+timedelta(minutes=minute+2)).isoformat(),o,h,l,c])
            events.write_text(json.dumps({'retouch_evidence':[candidate(side)]}),encoding='utf-8')
            specs=None if spec is None else {(T+120,side):spec}
            return simulate(src,events,horizon_mins=horizon,reward_r=1.5,structural_stops=specs)

    def test_anchor_is_known_and_sell_uses_synthetic_ask(self):
        specs=stop_specs([candidate(),candidate('SELL')],m15(),preentry(),spread=.6)
        self.assertEqual(specs[(T+120,'BUY')]['price'],90)
        self.assertAlmostEqual(specs[(T+120,'SELL')]['price'],110.6)
        self.assertEqual(specs[(T+120,'BUY')]['known_at'],T)

    def test_future_rows_cannot_change_anchor_or_preentry_validity(self):
        a=stop_specs([candidate()],m15(),preentry(),spread=.6)
        b=stop_specs([candidate()],m15()+[dict(close_time=T+900,low=1,high=500)],
                     preentry()+[dict(at=T+120,low=1,high=500)],spread=.6)
        self.assertEqual(a,b)

    def test_preentry_breach_and_missing_history_are_blocked(self):
        breached=preentry();breached[1]['low']=89
        for rows,reason in [(breached,'STRUCTURE_BREACHED_BEFORE_ENTRY'),(preentry()[:1],'UNKNOWN_PRE_ENTRY_HISTORY')]:
            spec=stop_specs([candidate()],m15(),rows,spread=.6)[(T+120,'BUY')]
            self.assertEqual(spec['blocked_reason'],reason)
            result=self.simulate_case(spec=spec)
            self.assertEqual(result['trades'],0)
            self.assertEqual(result['skipped_stop_policy'][0]['reason'],reason)

    def test_variable_distance_normalizes_timeout_and_tp(self):
        spec=dict(price=90,known_at=T)
        trade=self.simulate_case(spec=spec)['trades_detail'][0]
        self.assertAlmostEqual(trade['initial_stop_distance'],10.6)
        self.assertAlmostEqual(trade['target_assumed'],100.6+1.5*10.6)
        self.assertAlmostEqual(trade['r'],round((101-100.6)/10.6,5))

    def test_buy_and_sell_open_gap_losses_exceed_one_r(self):
        for side,spec,last_open in [('BUY',dict(price=90,known_at=T),80),
                                    ('SELL',dict(price=110.6,known_at=T),120)]:
            rows=[(0,100,101,99,100),(1,last_open,last_open+1,last_open-1,last_open)]
            trade=self.simulate_case(side=side,spec=spec,rows=rows)['trades_detail'][0]
            self.assertLess(trade['r'],-1)
        result=self.simulate_case(rows=[(0,100,101,99,100),(1,80,81,79,80)])
        self.assertLess(result['trades_detail'][0]['r'],-1)

    def test_invalid_current_side_stop_skipped_future_spec_rejected(self):
        result=self.simulate_case(spec=dict(price=100.3,known_at=T))
        self.assertEqual(result['trades'],0)
        self.assertEqual(result['skipped_stop_policy'][0]['reason'],'STOP_INVALID_AT_ENTRY')
        with self.assertRaises(ValueError):self.simulate_case(spec=dict(price=90,known_at=T+121))

    def test_gap_without_exit_is_unresolved(self):
        r=self.simulate_case(spec=dict(price=90,known_at=T),rows=[(0,100,101,99,100),(2,100,101,99,100)],horizon=3)
        self.assertEqual(r['trades'],0)
        self.assertEqual(r['skipped_incomplete'],1)

if __name__=='__main__':unittest.main()
