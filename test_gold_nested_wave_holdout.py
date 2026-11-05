import unittest
from pathlib import Path
from unittest.mock import patch

import orrery_gold_nested_wave_holdout as study


def bar(start, *, high=108):
    return dict(open_time=start, close_time=start + 300,
                open=104, high=high, low=103, close=104)


def candidate(at):
    return dict(candidate_id=str(at), family='A_CONTINUATION', side='BUY',
                known_at_utc=at, fill_verified=False, execution_allowed=False,
                structural_stop=100, indicative_close=104, known_room_price=6)


class HoldoutTests(unittest.TestCase):
    def test_incomplete_m15_is_not_constructed(self):
        self.assertEqual(study.complete_m15([bar(study.START), bar(study.START+600)]), [])

    def test_three_arms_and_boundary_exclusion(self):
        early = candidate(study.END-1800)
        late = dict(early, known_at_utc=study.END-900)
        bars = [bar(t) for t in range(study.END-1800, study.END-300, 300)]
        bars.append(bar(study.END-300, high=115))
        with patch.object(study, 'candidates', return_value=[
            (candidate(study.START-900), 'WAIT_EXPIRED', None),
            (early, 'RESUMED', late),
        ]):
            result = study.replay(bars)
        self.assertEqual(result['observed_m5'], 5)
        for arm in ('immediate', 'delayed', 'delayed_with_room_gate'):
            self.assertEqual(result[arm]['summary']['candidates'], 1)
            self.assertEqual(result[arm]['summary']['resolved'], 0)

    def test_past_archive_cannot_be_evaluated_as_holdout(self):
        with self.assertRaisesRegex(ValueError, 'No confirmed M5'):
            study.replay([bar(study.START-300)])

    def test_cli_blocks_before_frozen_end(self):
        with patch.object(study, 'END', float('inf')):
            with self.assertRaisesRegex(ValueError, 'has not ended'):
                study.run(Path('unused.csv'), '0' * 64)

    def test_receipt_binds_price_basis_and_counts_all_grid_gaps(self):
        start, end = study.START, study.START + 1500
        digest = 'a' * 64
        receipt = dict(instrument='OANDA:XAUUSD', timeframe='M5', price_basis='MID',
                       timestamp_convention='UTC_BAR_OPEN', confirmed_only=True,
                       csv_sha256=digest, acquisition_reference='offline fixture')
        with patch.object(study, 'END', end):
            audit = study.audit_source([bar(start+300), bar(start+900), bar(end-300)],
                                       receipt, digest)
            self.assertEqual(audit['observed_slots'], 2)
            self.assertEqual(audit['unobserved_slots'], 2)
            self.assertFalse(audit['session_calendar_verified'])
            for invalid in (dict(receipt, price_basis='BID'), dict(receipt, csv_sha256='b'*64)):
                with self.assertRaisesRegex(ValueError, 'Source receipt'):
                    study.audit_source([], invalid, digest)
