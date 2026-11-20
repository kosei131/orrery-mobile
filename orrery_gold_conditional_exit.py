# SPDX-License-Identifier: GPL-3.0-only
"""Test a predeclared profit-conditioned exit on fixed XAUUSD entries."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean

from orrery_gold_holding_comparison import (
    END, EVIDENCE, Q4_START, RESOLVED, START, TARGET_R,
    load_archive, load_q4, paired_exits, replay, signals,
)
from orrery_paired_archive_study import iso

COST = 0.30
TARGET_POSITIVE_RATE = 0.95


def net(row):
    return row['r'] - COST / row['initial_risk_price']


def stats(rows):
    known = [net(row) for row in rows if row['status'] == RESOLVED]
    wins = [r for r in known if r > 0]
    losses = [r for r in known if r < 0]
    unknown = len(rows)-len(known)
    win_sum, loss_sum = sum(wins), -sum(losses)
    return dict(entries=len(rows), resolved=len(known), unresolved=unknown, wins=len(wins),
                positive_rate=len(wins)/len(known) if known else None,
                all_entry_positive_rate_upper=(len(wins)+unknown)/len(rows) if rows else None,
                mean_r=mean(known) if known else None, pf=win_sum/loss_sum if losses else None,
                mean_win_r=mean(wins) if wins else None,
                mean_loss_r=-mean(losses) if losses else None,
                status=dict(Counter(row['status'] for row in rows)))


def measure(bid, ask, bars, start, end, expected):
    short, _ = replay(signals(bars, ask, end), bid, ask, TARGET_R, horizon=60)
    pairs = paired_exits(short, bid, ask)
    if len(pairs) != expected['fixed_entries'] or sum(a['status'] == b['status'] == RESOLVED
       for a, b in pairs) != expected['paired_resolved']:
        raise ValueError('Prior fixed-entry counts do not reproduce')
    groups = {'positive': [], 'nonpositive': []}
    policy = []
    for short_row, long_row in pairs:
        if short_row.get('exit_reason') != 'TIMEOUT_CLOSE':
            policy.append(short_row)
            continue
        group = 'positive' if net(short_row) > 0 else 'nonpositive'
        groups[group].append((short_row, long_row))
        policy.append(long_row if group == 'positive' else short_row)
    matched = [(a, b) for a, b in zip(short, policy) if a['status'] == b['status'] == RESOLVED]
    diagnostics = {}
    for name, group in groups.items():
        changes = [(net(a), net(b)) for a, b in group if b['status'] == RESOLVED]
        diagnostics[name] = dict(
            count=len(group), extension_resolved=len(changes),
            extension_unresolved=len(group)-len(changes),
            mean_change_r=mean(b-a for a, b in changes) if changes else None,
            extension_positive_rate=mean(b > 0 for _, b in changes) if changes else None,
            positive_to_nonpositive=sum(a > 0 >= b for a, b in changes),
            nonpositive_to_positive=sum(a <= 0 < b for a, b in changes),
        )
    return dict(start_utc=iso(start), end_utc_exclusive=iso(end), timeout_groups=diagnostics,
                baseline=stats(short), conditional=stats(policy),
                matched_baseline=stats([a for a, _ in matched]),
                matched_conditional=stats([b for _, b in matched]))


def run(root_2026, root_q4):
    raw = (EVIDENCE / 'gold_holding_comparison_summary.json').read_bytes()
    expected = json.loads(raw)
    bid, ask, _, bars, _, _ = load_archive(root_2026)
    recent = measure(bid, ask, bars, START, END, expected['historical_2026'])
    bid, ask, bars, _ = load_q4(root_q4)
    older = measure(bid, ask, bars, Q4_START, START, expected['separate_2025_q4'])
    return dict(source_revision=expected['source_revision'], evidence_sha256=sha256(raw).hexdigest(),
                cost=COST, target_positive_rate=TARGET_POSITIVE_RATE, historical_2026=recent,
                separate_2025_q4=older, diagnostic_allows_overlap=True, out_of_sample=False,
                account_return_pct=None, execution_allowed=False, adoption_allowed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_2026', type=Path)
    parser.add_argument('archive_2025_q4', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    payload = json.dumps(run(args.archive_2026, args.archive_2025_q4), indent=2, allow_nan=False)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(payload + '\n')
