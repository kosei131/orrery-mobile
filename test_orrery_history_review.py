from hashlib import sha256
from pathlib import Path
import unittest
from unittest.mock import patch
import test_orrery_mt5_history_check as fixture
Feed = fixture.Feed
from orrery_mt5_history_check import check_history
from orrery_history_review import review_history, main
from lsr04_tick_archive import _encode, _decode


class OfflineReviewTests(unittest.TestCase):
    setUp = fixture.HistoryCheckTests.setUp

    def capture(self, spread=.1):
        feed = Feed(); feed.spread = spread
        check_history(feed, **self.args)
        return sha256((self.output/'history_check.json').read_bytes()).hexdigest()

    def test_recomputes_quality_without_terminal_or_profit(self):
        pin = self.capture()
        result = review_history(self.output, expected_receipt_sha256=pin)
        self.assertTrue(result['local_integrity_verified'])
        self.assertEqual(result['status'], 'LOCAL_HISTORY_REVIEW_REQUIRED')
        self.assertEqual(result['rows'], 600)
        self.assertIn('NO_SESSION_CALENDAR', result['review_reasons'])
        for key in ('completeness_verified','backtest_ready','profitability_evaluated',
                    'execution_allowed','broker_authenticity_verified','source_execution_attested'):
            self.assertIs(result[key], False)

    def test_retained_pin_required(self):
        self.capture()
        with self.assertRaises(ValueError): review_history(self.output, expected_receipt_sha256='0'*64)

    def test_raw_tick_tampering_rejected(self):
        pin = self.capture()
        path = self.output/'archive'/'ticks.jsonl'
        path.write_bytes(path.read_bytes().replace(b'2000.0', b'1999.0', 1))
        with self.assertRaises(ValueError): review_history(self.output, expected_receipt_sha256=pin)

    def test_missing_completion_rejected(self):
        pin = self.capture(); (self.output/'history_check.json').unlink()
        with self.assertRaises(ValueError): review_history(self.output, expected_receipt_sha256=pin)

    def test_request_tampering_rejected(self):
        pin = self.capture(); (self.output/'request.json').write_text('{}')
        with self.assertRaises(ValueError): review_history(self.output, expected_receipt_sha256=pin)

    def test_reanchored_receipt_cannot_claim_profit_or_wrong_count(self):
        self.capture(); path = self.output/'history_check.json'; original = _decode(path.read_bytes())
        for changes in (dict(profitability_evaluated=True), dict(rows=601), dict(review_reasons=[])):
            data = _encode(dict(original, **changes)); path.write_bytes(data)
            with self.assertRaises(ValueError):
                review_history(self.output, expected_receipt_sha256=sha256(data).hexdigest())

    def test_quality_failure_stays_blocked(self):
        pin = self.capture(spread=2.)
        result = review_history(self.output, expected_receipt_sha256=pin)
        self.assertEqual(result['status'], 'BLOCKED_HISTORY_QUALITY')
        self.assertIn('excessive_spread_rows', result['issues'])

    def test_cli_preserves_intake_and_refuses_overwrite(self):
        pin = self.capture(); output = Path(self.temp.name)/'review.json'
        argv = ['review', '--run', str(self.output), '--receipt-sha256', pin, '--output', str(output)]
        with patch('sys.argv', argv), patch('builtins.print'):
            self.assertEqual(main(), 0)
            before = output.read_bytes()
            self.assertEqual(main(), 1)
            self.assertEqual(output.read_bytes(), before)
        self.assertEqual(sha256((self.output/'history_check.json').read_bytes()).hexdigest(), pin)


if __name__ == '__main__': unittest.main()
