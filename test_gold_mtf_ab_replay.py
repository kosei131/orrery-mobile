import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
from orrery_gold_mtf_ab_replay import run, _recent, _context

def candle(t,lo,hi,op,cl):
    return dict(close_time=t,low=lo,high=hi,open=op,close=cl)

def fixtures():
    h4=[candle(14400,80,110,105,105),
        candle(28800,90,120,105,105),
        candle(43200,100,130,105,105)]
    m15=[candle(t,105,115,110,110) for t in range(34200,45001,900)]
    m15[-2]=candle(44100,100,114,110,108)
    m5=[candle(t,105,110,108,108) for t in range(39900,45001,300)]
    m5[-1]=candle(45000,109,114,110,111)
    return {'H4':h4,'M15':m15,'M5':m5}

class MTFReplayTests(TestCase):
    def setUp(self):
        tmp=TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.source=self.root/'source.csv'
        self.source.write_bytes(b'example pinned sample source')
        self.pin=hashlib.sha256(self.source.read_bytes()).hexdigest()
        for tf in ('H4','M15','M5'):
            (self.root/f'XAUUSD_{tf}_UNVERIFIED_QUOTE.csv').write_bytes(tf.encode())
        self.bars_pins={tf:hashlib.sha256(tf.encode()).hexdigest()
                        for tf in ('H4','M15','M5')}

    def replay(self,data):
        def mock_load(path,tf):
            return dict(bars=data[tf])
        with mock.patch('orrery_gold_mtf_ab_replay.load',side_effect=mock_load):
            return run(self.source,self.root,expected_source_sha256=self.pin,
                       expected_bars_sha256=self.bars_pins)

    def test_A_candidate_once_without_filled_trade(self):
        x=self.replay(fixtures())
        self.assertEqual(x['candidate_counts']['A_CONTINUATION'],1)
        self.assertEqual(x['candidate_counts']['B_COUNTER_SWEEP'],0)
        self.assertIsNone(x['actual_win_rate_pct'])
        self.assertIsNone(x['net_expectancy_r'])
        self.assertFalse(x['execution_allowed'])

    def test_m15_gap_rejects_candidate(self):
        d=fixtures()
        d['M15'][-3]['close_time']-=900
        x=self.replay(d)
        self.assertEqual(x['candidate_counts']['A_CONTINUATION'],0)
        self.assertGreater(x['missing_or_gapped_context'],0)

    def test_unknown_source_rejected(self):
        with self.assertRaises(ValueError):
            run(self.source,self.root,expected_source_sha256='0'*64)

    def test_recent_requires_contiguous_h4(self):
        h=fixtures()['H4']
        h[-2]['close_time']-=14400
        self.assertEqual(_recent(h,[b['close_time'] for b in h],45000,'H4'),[])

    def test_changed_aggregated_m5_hash_rejected(self):
        d=fixtures()
        (self.root/'XAUUSD_M5_UNVERIFIED_QUOTE.csv').write_bytes(b'bad M5')
        with self.assertRaisesRegex(ValueError, 'M5 normalized OHLC SHA256 mismatch'):
            self.replay(d)

    def test_missing_aggregated_hash_pin_rejected(self):
        d=fixtures()
        self.bars_pins.pop('M15')
        with self.assertRaises(ValueError):
            self.replay(d)

    def test_zero_future_leakage(self):
        d=fixtures()
        a=self.replay(d)
        d['M5'].append(candle(45300,100,150,110,110))
        b=self.replay(d)
        before=[x for x in b['candidates'] if x['known_at_utc']<=45000]
        self.assertEqual(before,a['candidates'])

    def test_diagnostic_identifies_noncontiguous_m15(self):
        d=fixtures()
        d['M15'][-3]['close_time']-=900
        r=self.replay(d)
        self.assertGreater(r['context_failure_counts']['M15_NONCONTIGUOUS_BARS'],0)
        self.assertTrue(r['context_failures_may_overlap_across_timeframes'])

    def test_diagnostic_distinguishes_stale_h4(self):
        d=fixtures()
        d['H4']=[candle(-28800,80,110,105,105),
                 candle(-14400,90,120,105,105),
                 candle(0,100,130,105,105)]
        r=self.replay(d)
        self.assertGreater(r['context_failure_counts']['H4_STALE_LAST_CLOSE'],0)
        self.assertEqual(r['candidate_counts']['A_CONTINUATION'],0)

    def test_short_history_is_not_misreported_as_no_signal(self):
        d=fixtures()
        d['H4']=d['H4'][-2:]
        r=self.replay(d)
        self.assertGreater(r['context_failure_counts']['H4_INSUFFICIENT_HISTORY'],0)
        self.assertEqual(r['examined_m5_bars'],0)

    def test_context_reason_ready(self):
        d=fixtures()
        a=d['H4']
        bars,status=_context(a,[b['close_time'] for b in a],45000,'H4')
        self.assertEqual(status,'READY')
        self.assertEqual(len(bars),3)

