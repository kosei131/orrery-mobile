from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from orrery_mt5_candidate_probe import _request, probe_latest
from test_orrery_mt5_history_check import Feed


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.path = self.root/'reference.json'; self.output = self.root/'new'
        self.now = datetime(2026,11,1,tzinfo=timezone.utc)
        self.start = datetime(2026,10,30,3,30,tzinfo=timezone.utc)
        self.t = int(self.start.timestamp())
        self.report = dict(status='EXPLORATORY_WINDOW_RESET_GROSS_REFERENCE_ONLY',execution_allowed=False,
            actual_profit_usd=None,zip_sha256='0'*64,
            bundle_audit=dict(zip_sha256='0'*64,source_declared='OANDA:XAUUSD via TradingView MCP'),
            candidates=[self.row(self.t-86400,'BUY','CLOSED_REFERENCE'),self.row(self.t,'SELL','CENSORED_AT_WINDOW_END')])
        self.pin = self.save()

    def row(self, t, side, outcome):
        return dict(entry_reference_at_s=t,reference_status=outcome,
            plan=dict(id=f'XAUUSD:{t}:{side}',symbol='XAUUSD',side=side,known_at_msc=t*1000))

    def save(self):
        raw = json.dumps(self.report).encode(); self.path.write_bytes(raw)
        return sha256(raw).hexdigest()

    def probe(self, feed=None, **kw):
        args = dict(reference=self.path,reference_sha256=self.pin,output=self.output,now=self.now)
        args.update(kw)
        return probe_latest(Feed() if feed is None else feed,**args)

    def test_latest_selection_uses_clock_not_winning_outcome(self):
        r = _request(self.path,self.pin,self.now)
        self.assertEqual(r['candidate_id'],f'XAUUSD:{self.t}:SELL')
        self.assertEqual(datetime.fromisoformat(r['start_utc']),self.start)
        self.assertEqual(datetime.fromisoformat(r['end_utc']),self.start+timedelta(minutes=10))
        self.assertFalse(r['full_trade_horizon_requested'])

    def test_historical_capture_reuses_archive_and_keeps_costs_unknown(self):
        result = self.probe()
        self.assertEqual(result['history']['rows'],600)
        self.assertEqual(result['status'],'DEMO_CANDIDATE_PROBE_SAVED_REVIEW_REQUIRED')
        self.assertTrue((self.output/'history/archive/ticks.jsonl').exists())
        self.assertTrue((self.output/'probe.json').exists())
        for key in ('commission_per_lot_usd','carry_cost_usd','slippage','actual_profit_usd'):
            self.assertIsNone(result[key])
        for key in ('execution_allowed','backtest_ready','profitability_evaluated','mt5_feed_matches_tradingview_verified'):
            self.assertFalse(result[key])
        for p in self.output.rglob('*.json'):
            self.assertNotIn('private',p.read_text()); self.assertNotIn('login',p.read_text())
        self.assertEqual(sha256(self.path.read_bytes()).hexdigest(),self.pin)

    def test_reference_tamper_or_permission_mismatch_stops_before_mt5(self):
        class Never:
            def account_info(self): raise AssertionError('Must validate pin first')
        self.path.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.probe(Never())
        self.report['execution_allowed'] = True; self.pin=self.save()
        with self.assertRaises(ValueError):self.probe(Never())
        self.assertFalse(self.output.exists())

    def test_real_account_and_changed_account_stop(self):
        feed = Feed(); feed.mode=2
        with self.assertRaises(ValueError):self.probe(feed)
        self.assertFalse(self.output.exists())
        feed = Feed(); feed.switch=True
        with self.assertRaises(ValueError):self.probe(feed)
        self.assertFalse((self.output/'probe.json').exists())

    def test_empty_history_keeps_incomplete_request_without_success_marker(self):
        feed=Feed();feed.empty=True
        with self.assertRaises(ValueError):self.probe(feed)
        self.assertTrue((self.output/'request.json').exists())
        self.assertFalse((self.output/'probe.json').exists())

    def test_bad_tick_quality_receipt_is_blocked_and_keeps_evidence(self):
        feed=Feed();feed.spread=2
        r=self.probe(feed)
        self.assertEqual(r['status'],'BLOCKED_CANDIDATE_PROBE_QUALITY')
        self.assertTrue((self.output/'history/archive/ticks.jsonl').exists())
        self.assertFalse(r['backtest_ready'])

    def test_existing_folder_not_overwritten(self):
        self.output.mkdir(); sentinel=self.output/'sentinel';sentinel.write_text('keep')
        with self.assertRaises(FileExistsError):self.probe()
        self.assertEqual(sentinel.read_text(),'keep')

    def test_future_clock_or_noncanonical_duplicate_candidates_rejected(self):
        with self.assertRaises(ValueError):self.probe(now=self.start)
        self.report['candidates'][1]['plan']['symbol']='USDJPY';self.pin=self.save()
        with self.assertRaises(ValueError):self.probe()
        self.report['candidates']=[self.row(self.t,'SELL','UNKNOWN')]*2;self.pin=self.save()
        with self.assertRaises(ValueError):self.probe()
        self.assertFalse(self.output.exists())

    def test_reference_clock_mismatch_and_naive_now_rejected(self):
        self.report['candidates'][1]['plan']['known_at_msc']+=1;self.pin=self.save()
        with self.assertRaises(ValueError):self.probe()
        with self.assertRaises(ValueError):self.probe(now=self.now.replace(tzinfo=None))


if __name__=='__main__':unittest.main()
