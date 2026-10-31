"""Real archive/account paths with injected fake DEMO, never market results."""
import json
from pathlib import Path
import unittest
from orrery_research_summary import audit_completed_run, build_summary, main
from orrery_research_worker import digest
from lsr04_tick_archive import _encode
import test_orrery_research_worker as fixture


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.WorkerTests(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.receipt = self.fixture.job(); self.root = self.fixture.folder(self.receipt)

    def summary(self): return build_summary(self.root, self.receipt)

    def blocked(self):
        value = self.summary()
        self.assertEqual(value['audit_status'], 'AUDIT_BLOCKED'); self.assertIsNone(value['accounts'])
        self.assertFalse(value['execution_allowed'])

    def rewrite_report(self, change):
        # Test an independently supplied result with a consistent new pin, so
        # schema/accounting/privacy checks are exercised beyond hash rejection.
        p = self.root/'account'/'account_report.json'; report = json.loads(p.read_bytes())
        change(report); p.write_bytes(_encode(report))
        p = self.root/'account'/'account_run.json'; marker = json.loads(p.read_bytes())
        marker['files_sha256']['account_report.json'] = digest((self.root/'account'/'account_report.json').read_bytes())
        p.write_bytes(_encode(marker)); self.receipt['account_run_sha256'] = digest(p.read_bytes())
        for name in ('status.json', 'job_complete.json'):
            p = self.root/name; value = json.loads(p.read_bytes())
            value['account_run_sha256'] = self.receipt['account_run_sha256']; p.write_bytes(_encode(value))

    def test_full_chain_and_zero_trades_remain_unknown_win_rate(self):
        value = audit_completed_run(self.root, self.receipt)
        self.assertEqual(value['audit_status'], 'CONSISTENT_RESEARCH_ARTIFACTS')
        self.assertEqual(set(value['accounts']), {'CONFIRMATION','RETEST'})
        for account in value['accounts'].values():
            self.assertEqual(account['closed_trades'], 0)
            self.assertIsNone(account['win_rate_fraction']); self.assertIsNone(account['profit_factor'])
        self.assertFalse(value['pnl_recomputed']); self.assertFalse(value['worker_liveness_verified'])
        self.assertFalse(value['market_edge_verified'])

    def test_missing_marker_or_failed_state_never_produces_metrics(self):
        (self.root/'job_complete.json').unlink(); self.blocked()

    def test_failed_status_blocks_even_when_final_marker_exists(self):
        p = self.root/'status.json'; value = json.loads(p.read_bytes()); value['state'] = 'FAILED'
        p.write_bytes(_encode(value)); self.blocked()

    def test_receipt_pin_or_run_identity_mismatch(self):
        self.receipt['capture_run_sha256'] = '0'*64; self.blocked()
        self.receipt['run_id'] = '../outside'; self.blocked()

    def test_report_byte_tamper_blocks(self):
        p = self.root/'account'/'account_report.json'; p.write_bytes(p.read_bytes()+b' '); self.blocked()

    def test_raw_ticks_tamper_reruns_archive_audit(self):
        p = next((self.root/'capture'/'ticks').rglob('ticks.jsonl'))
        p.write_bytes(p.read_bytes()+b'{}\n'); self.blocked()

    def test_fixed_settings_and_code_copy_tamper(self):
        p = self.root/'settings.json'; p.write_bytes(p.read_bytes()+b' '); self.blocked()

    def test_code_manifest_copy_must_match_retained_source_pin(self):
        p = self.root/'code_manifest.json'; p.write_bytes(p.read_bytes()+b' '); self.blocked()

    def test_sentinels_in_free_text_are_never_projected(self):
        secret = 'PRIVATE_LOGIN_9876_SERVER_C_USERS_PERSON'
        def change(report):
            report['raw_error'] = secret; report['bar_source'] = secret; report['caveat'] = secret
            for account in report['accounts'].values():
                account['cost_source'] = secret; account['limitations'] = secret
                account['raw_position'] = {'login': secret}
        self.rewrite_report(change)
        value = self.summary(); self.assertEqual(value['audit_status'], 'CONSISTENT_RESEARCH_ARTIFACTS')
        serialized = json.dumps(value)
        for private in (secret, str(self.fixture.terminal), 'FAKE_DEMO', 'demo_account_scope_sha256', 'cost_source'):
            self.assertNotIn(private, serialized)

    def test_claimed_win_rate_blocks(self):
        self.rewrite_report(lambda r: r['accounts']['CONFIRMATION']['closed_statistics'].update(win_rate=.95))
        self.blocked()

    def test_nonfinite_metric_rejected_by_projection(self):
        from orrery_research_summary import _account_summary
        p = self.root/'account'/'account_report.json'
        account = json.loads(p.read_bytes())['accounts']['CONFIRMATION']
        account['ending_equity_usd'] = float('inf')
        with self.assertRaises(ValueError): _account_summary(account)

    def test_closed_net_statistics_recomputed_from_saved_trade_ledger(self):
        from orrery_research_summary import _account_summary
        from lsr02_risk_plan import performance
        a = json.loads((self.root/'account'/'account_report.json').read_bytes())['accounts']['CONFIRMATION']
        a['trades'] = [dict(id='loss', closed_at=1, gross_pnl=-1, cost=1, initial_risk=1, net_usd=-2),
                       dict(id='win', closed_at=2, gross_pnl=2, cost=1, initial_risk=1, net_usd=1)]
        stats = performance(a['trades'], initial_equity=3000)
        a['closed_statistics'] = {k:stats[k] for k in a['closed_statistics']}
        a.update(closed_trade_net_usd=-1, ending_balance_usd=2999, ending_equity_usd=2998,
                 balance_change_usd=-1, equity_change_usd=-2, max_sampled_equity_drawdown_usd=3,
                 open_position={'id':'NOT_FOR_OUTPUT'}, max_consecutive_losses=1)
        value = _account_summary(a)
        self.assertEqual(value['closed_trades'], 2); self.assertEqual(value['win_rate_fraction'], .5)
        self.assertEqual(value['expectancy_r'], -.5); self.assertEqual(value['profit_factor'], .5)
        self.assertEqual(value['open_positions'], 1)
        a['trades'][0]['net_usd'] = 0
        with self.assertRaises(ValueError): _account_summary(a)

    def test_wrong_costs_even_when_reanchored_block(self):
        self.rewrite_report(lambda r: r['config'].update(round_trip_cost_per_lot_usd=0))
        self.blocked()

    def test_unsafe_flags_even_when_reanchored_block(self):
        self.rewrite_report(lambda r: r.update(execution_allowed=True)); self.blocked()

    def test_missing_mode_blocks(self):
        self.rewrite_report(lambda r: r['accounts'].pop('RETEST')); self.blocked()

    def test_open_position_preserved_as_count_without_ids(self):
        def change(report):
            a = report['accounts']['CONFIRMATION']; a['open_position'] = {'id':'PRIVATE_POSITION_ID'}
        self.rewrite_report(change)
        value = self.summary(); self.assertEqual(value['accounts']['CONFIRMATION']['open_positions'], 1)
        self.assertNotIn('PRIVATE_POSITION_ID', json.dumps(value))

    def test_cli_writes_new_file_only_and_sanitizes_failures(self):
        from unittest.mock import patch
        receipt_path = self.fixture.root/'receipt.json'; receipt_path.write_bytes(b'\xef\xbb\xbf'+_encode(self.receipt))
        output = self.fixture.root/'summary.json'
        args = ['--run', str(self.root), '--receipt', str(receipt_path), '--output', str(output)]
        with patch('builtins.print'):
            self.assertEqual(main(args), 0); original = output.read_bytes()
            self.assertEqual(main(args), 1); self.assertEqual(output.read_bytes(), original)
            (self.root/'job_complete.json').unlink(); args[-1] = str(self.fixture.root/'blocked.json')
            self.assertEqual(main(args), 2)
        self.assertIsNone(json.loads((self.fixture.root/'blocked.json').read_bytes())['accounts'])


if __name__ == '__main__': unittest.main()
