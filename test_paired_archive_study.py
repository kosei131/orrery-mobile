import csv
from pathlib import Path
import tempfile
import unittest
from orrery_paired_archive_study import evaluate_plan,read_side,summary

T=1735689600

def candle(o=100,h=101,l=99,c=100):return dict(open=o,high=h,low=l,close=c)
def plan(side='BUY'):return dict(first_poi_touch_close=T,side=side)


class PairedArchiveTests(unittest.TestCase):
    def test_buy_pays_ask_and_sells_bid(self):
        r=evaluate_plan(plan(),{T:candle(h=111)},{T:candle(o=100.5,h=112,l=100,c=101)})
        self.assertEqual(r['entry'],100.5);self.assertEqual(r['target'],109.5)
        self.assertEqual(r['r'],1.5);self.assertEqual(r['exit_reason'],'TP_TOUCH')
    def test_sell_pays_ask_to_exit(self):
        bid={T:candle(h=100.5,l=90,c=91)}
        ask={T:candle(o=100.5,h=101,l=91.5,c=92)}
        r=evaluate_plan(plan('SELL'),bid,ask,horizon=1)
        self.assertEqual(r['entry'],100);self.assertEqual(r['exit_reason'],'TIMEOUT_CLOSE')
        self.assertAlmostEqual(r['r'],8/6)
    def test_same_minute_dual_touch_remains_unknown(self):
        r=evaluate_plan(plan(),{T:candle(h=112,l=90)},{T:candle(o=100.5)})
        self.assertEqual(r['status'],'AMBIGUOUS_SAME_MINUTE');self.assertIsNone(r['r'])
        self.assertEqual(r['stop_first_reference_r'],-1)
        self.assertIsNone(summary([r])['mean_resolved_reference_r'])
    def test_stop_before_later_side_gap_is_preserved(self):
        r=evaluate_plan(plan(),{T:candle(l=94)},{T:candle(o=100.5)},horizon=2)
        self.assertEqual(r['r'],-1)
        r=evaluate_plan(plan(),{T:candle(),T+120:candle(h=120)},{T:candle(o=100.5),T+120:candle()},horizon=3)
        self.assertEqual(r['status'],'CENSORED_AT_SIDE_GAP')
    def test_open_gap_loss_is_not_clamped(self):
        bid={T:candle(),T+60:candle(o=90,h=91,l=89,c=90)}
        ask={T:candle(o=100.5),T+60:candle(o=90.5,h=91.5,l=89.5,c=90.5)}
        r=evaluate_plan(plan(),bid,ask,horizon=2)
        self.assertAlmostEqual(r['r'],-1.75);self.assertEqual(r['exit_reason'],'STOP_AT_OBSERVED_OPEN')
    def test_structure_breach_and_missing_history_are_not_losses(self):
        bid={T-60:candle(l=98),T:candle()};ask={T-60:candle(o=100.5),T:candle(o=100.5)}
        r=evaluate_plan(plan(),bid,ask,structural_stop=99,structural_known_at=T-60)
        self.assertEqual(r['status'],'STRUCTURE_BREACHED_BEFORE_ENTRY')
        r=evaluate_plan(plan(),{T:candle()},{T:candle(o=100.5)},structural_stop=99,structural_known_at=T-60)
        self.assertEqual(r['status'],'UNKNOWN_PRE_ENTRY_HISTORY')
        with self.assertRaises(ValueError):evaluate_plan(plan(),bid,ask,structural_stop=99,structural_known_at=T+60)
    def test_invalid_initial_stop_never_becomes_filled_trade(self):
        r=evaluate_plan(plan(),{T:candle()},{T:candle(o=110,h=111,l=109,c=110)})
        self.assertEqual(r['status'],'STOP_INVALID_AT_ENTRY')
    def test_side_audit_detects_flat_rows_and_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'s.csv'
            def write(times):
                with p.open('w',newline='') as f:
                    w=csv.writer(f);w.writerow(['timestamp','open','high','low','close'])
                    for t in times:w.writerow([t*1000,100,100,100,100])
            write([T,T+60,T+120]);_,a=read_side(p)
            self.assertEqual(a['longest_identical_flat_minutes'],3)
            write([T,T])
            with self.assertRaises(ValueError):read_side(p)


class PairedEvidenceTests(unittest.TestCase):
    def test_paired_file_pins_and_all_population_counts(self):
        import json
        from orrery_paired_archive_study import SOURCE_PINS
        r=json.loads(Path('research_evidence/local-history-20261101/paired_archive_study_20261102.json').read_text())
        self.assertEqual(r['bid_rows'],47608);self.assertEqual(r['shared_rows'],47608)
        self.assertEqual(r['ask_only'],0);self.assertEqual(r['bid_only'],0)
        for f in r['files']:
            self.assertEqual(f['sha256'],SOURCE_PINS[f['side']+'_'+f['month']+'.csv'])
        for w in r['results'].values():
            self.assertEqual(len(w['models']),8)
            for m in w['models'].values():
                self.assertEqual(m['entry_plans']+sum(m['no_entry_reasons'].values()),m['confirmation_universe'])
                self.assertEqual(sum(m['status_counts'].values()),m['entry_plans'])
                self.assertEqual(len(m['outcomes']),m['entry_plans'])
                resolved=[x for x in m['outcomes'] if x['status']=='RESOLVED_REFERENCE']
                self.assertEqual(len(resolved),m['resolved'])
                self.assertEqual(sum(x['r']>0 for x in resolved),m['positive'])
                self.assertIsNone(m['net_expectancy_r']);self.assertIsNone(m['account_return_pct'])
        self.assertFalse(r['source_authenticity_verified']);self.assertFalse(r['execution_allowed'])
        self.assertFalse(r['independent_holdout_verified'])
    def test_sell_structure_uses_ask_history_and_missing_side_is_unknown(self):
        bid={T-60:candle(),T:candle()};ask={T-60:candle(o=100.5,h=106),T:candle(o=100.5)}
        r=evaluate_plan(plan('SELL'),bid,ask,structural_stop=105,structural_known_at=T-60)
        self.assertEqual(r['status'],'STRUCTURE_BREACHED_BEFORE_ENTRY')
        r=evaluate_plan(plan(),{T:candle()},{})
        self.assertEqual(r['status'],'UNKNOWN_ENTRY_HISTORY')
        self.assertIsNone(summary([r])['positive_rate_pct'])

if __name__=='__main__':unittest.main()
