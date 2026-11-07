# SPDX-License-Identifier: GPL-3.0-only
"""Integrity checked archived entry comparison; never a live trading signal."""
from hashlib import sha256
import json
from pathlib import Path

MODES = ('CONFIRMATION_FIXED_6', 'CONFIRMATION_SWEEP_EXTREME',
         'RETEST_FIXED_6', 'RETEST_SWEEP_EXTREME')


def load_panel(path, expected_sha256):
    with Path(path).open('rb') as stream:
        raw = stream.read(1024*1024+1)
    if len(raw) > 1024*1024 or sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Entry archive size/hash mismatch')
    def reject(value):
        raise ValueError('Non-finite entry archive')
    r = json.loads(raw, parse_constant=reject)
    if r.get('status') != 'EXPLORATORY_ENTRY_OPPORTUNITY_REAUDIT_NOT_LSR02':
        raise ValueError('Exploratory entry archive required')
    for key in ('out_of_sample', 'formal_lsr02', 'h4_filter_applied',
                'halftrend_compared', 'reversal04_compared', 'execution_allowed', 'adopted'):
        if r.get(key) is not False:
            raise ValueError('Incompatible research scope: '+key)
    for key in ('actual_profit_usd', 'account_return_pct', 'account_max_dd_usd', 'net_expectancy_r'):
        if key not in r or r[key] is not None:
            raise ValueError('Unknown account metrics required')
    def count(value):
        if type(value) is not int or value < 0:
            raise ValueError('Nonnegative integer count required')
        return value
    universe = count(r['confirmation_universe'])
    if set(r['results']) != set(MODES):
        raise ValueError('All four entry/stop models required')
    for mode in MODES:
        v = r['results'][mode]; o = v['entry_outcomes']
        plans = count(v['entry_plans']); resolved = count(o['resolved_outcomes'])
        unknown = count(o['unresolved_or_unmodeled']); wins = count(o['wins'])
        no_entry = sum(count(n) for n in v['no_entry_reasons'].values())
        skips = sum(count(n) for n in v['stop_policy_skip_counts'].values())
        incomplete = count(v['incomplete_after_entry'])
        exits = sum(count(n) for n in v['exit_reason_counts'].values())
        if (plans != count(o['candidates']) or plans + no_entry != universe
                or resolved + unknown != plans or skips + incomplete != unknown
                or exits != resolved or wins > resolved):
            raise ValueError('Entry archive population accounting mismatch')
        rate = round(100*wins/resolved, 2) if resolved else None
        if o['win_rate_pct'] != rate:
            raise ValueError('Resolved-only win rate mismatch')
    # No candidate plans, live overlays, or inferred account returns.
    return dict(status='ARCHIVED_EXPLORATORY_ENTRY_COMPARISON',
                report_sha256=expected_sha256, source_sha256=r['source_sha256'],
                comparison_period_utc=r['comparison_period_utc'],
                confirmation_universe=universe, assumptions=r['assumptions'],
                results=r['results'], execution_allowed=False, adopted=False)
