# SPDX-License-Identifier: GPL-3.0-only
"""Fixed-candidate Gold first-touch cohort, research price observations only.

The source ZIP is intentionally not downloaded, guessed, or combined here.
Each candidate carries its original tick source SHA and a bounded raw quote
window of that very same source; missing/mismatched inputs are retained as
censored records. No candidate selection using observed outcomes is allowed.
"""
from collections import Counter
from orrery_gold_barrier_window import compare_barriers

MAX_CANDIDATES = 1000


def audit_cohort(candidates, *, expected_tick_sha256):
    if (not isinstance(expected_tick_sha256, str)
        or len(expected_tick_sha256) != 64
        or any(c not in '0123456789abcdef' for c in expected_tick_sha256)):
        raise ValueError('Pinned lowercase source SHA256 required')
    if not isinstance(candidates, (list, tuple)) or len(candidates) > MAX_CANDIDATES:
        raise ValueError('Bounded candidate sequence required')
    seen = set()
    records = []
    all_targets = None
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError('Candidate mapping required')
        ident = candidate.get('candidate_id')
        if not isinstance(ident, str) or not ident or len(ident) > 128 or ident in seen:
            raise ValueError('Unique fixed candidate ID required')
        seen.add(ident)
        targets = candidate.get('targets')
        if not isinstance(targets, dict) or not targets:
            raise ValueError('Fixed target map required')
        if all_targets is None:
            all_targets = tuple(targets)
        if set(targets) != set(all_targets):
            raise ValueError('Identical named target groups required')
        record = dict(candidate_id=ident, target_results={},
                      price_observation_only=True, execution_allowed=False)
        if candidate.get('symbol') != 'XAUUSD':
            raise ValueError('Gold-only cohort')
        if candidate.get('source_sha256') != expected_tick_sha256:
            status = 'CENSORED_SOURCE_MISMATCH'
        elif candidate.get('quotes') is None:
            status = 'CENSORED_QUOTES_UNAVAILABLE'
        else:
            compared = compare_barriers(
                candidate['quotes'], entry_utc_ms=candidate['entry_utc_ms'],
                side=candidate['side'], stop=candidate['stop'], targets=targets)
            record['target_results'] = compared['target_results']
            status = 'OBSERVED_OR_CENSORED_PER_TARGET'
        if status != 'OBSERVED_OR_CENSORED_PER_TARGET':
            record['target_results'] = {
                name: dict(status=status, at_utc_ms=None, broker_fill_verified=False,
                           actual_profit_usd=None) for name in targets}
        record['status'] = status
        records.append(record)
    group_counts = {
        name: dict(Counter(r['target_results'][name]['status'] for r in records))
        for name in (all_targets or ())}
    return dict(status='FIXED_GOLD_PRICE_OBSERVATION_COHORT_ONLY',
                source_sha256=expected_tick_sha256, candidate_count=len(records),
                target_status_counts=group_counts, records=records,
                actual_win_rate_pct=None, net_expectancy_r=None,
                account_return_pct=None, broker_fills_verified=False,
                execution_allowed=False)
