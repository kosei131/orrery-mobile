# SPDX-License-Identifier: GPL-3.0-only
"""Compare Gold exits on fixed entries selected by the 60-minute policy."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean

from orrery_gold_compression_study import END, START, Q4_START, TARGET_R, signals
from orrery_gold_pullback_study import describe, evaluate_pullback, load_archive, replay
from orrery_gold_session_breakout import load_q4

EVIDENCE = Path(__file__).with_name('research_evidence') / 'local-history-20261101'
RESOLVED = 'RESOLVED_REFERENCE'


def paired_exits(short, bid, ask):
    pairs = []
    for row in short:
        extended = evaluate_pullback(
            {'first_poi_touch_close': row['at_utc'], 'side': row['side']}, bid, ask,
            structural_stop=row['stop'], structural_known_at=row['setup_at_utc'],
            horizon=240, target_r=TARGET_R,
        )
        pairs.append((row, dict(extended, at_utc=row['at_utc'])))
    return pairs


def measure(bid, ask, bars, start, end, baseline):
    candidates = list(signals(bars, ask, end))
    short, short_skips = replay(candidates, bid, ask, TARGET_R, horizon=60)
    long, long_skips = replay(candidates, bid, ask, TARGET_R, horizon=240)
    for horizon, rows, skips in ((60, short, short_skips), (240, long, long_skips)):
        actual = dict(describe(rows, start, end), raw_signals=len(candidates), occupied_skips=skips)
        if actual != baseline[f'all_{horizon}']:
            raise ValueError(f'Archived {horizon}-minute baseline does not reproduce')
    pairs = paired_exits(short, bid, ask)
    matched = [(a, b) for a, b in pairs if a['status'] == b['status'] == RESOLVED]
    if any(a['entry'] != b['entry'] or a['initial_risk_price'] != b['initial_risk_price']
           for a, b in matched):
        raise ValueError('Entry or risk changed on the same clock')
    deltas = [b['r']-a['r'] for a, b in matched]
    timeouts = [(a, b) for a, b in pairs if a.get('exit_reason') == 'TIMEOUT_CLOSE']
    timeout_deltas = [b['r']-a['r'] for a, b in timeouts if b['status'] == RESOLVED]
    short_clocks = {row['at_utc'] for row in short}
    long_clocks = {row['at_utc'] for row in long}
    return dict(
        baseline_reproduced=True,
        fixed_entries=len(short),
        paired_resolved=len(matched),
        paired_unresolved=len(pairs)-len(matched),
        status_transitions=dict(Counter(f"{a['status']} -> {b['status']}" for a, b in pairs)),
        same_entry_60=describe([a for a, _ in matched], start, end),
        same_entry_240=describe([b for _, b in matched], start, end),
        mean_paired_delta_r=mean(deltas) if deltas else None,
        timeout_60_count=len(timeouts),
        timeout_60_extension_statuses=dict(Counter(b['status'] for _, b in timeouts)),
        timeout_mean_paired_delta_r=mean(timeout_deltas) if timeout_deltas else None,
        timeout_improved=sum(delta > 1e-12 for delta in timeout_deltas),
        timeout_worsened=sum(delta < -1e-12 for delta in timeout_deltas),
        timeout_unchanged=sum(abs(delta) <= 1e-12 for delta in timeout_deltas),
        independent_60=baseline['all_60'],
        independent_240=baseline['all_240'],
        independent_clock_overlap=len(short_clocks & long_clocks),
        independent_60_only=len(short_clocks-long_clocks),
        independent_240_only=len(long_clocks-short_clocks),
    )


def run(root_2026, root_q4):
    raw = (EVIDENCE / 'gold_compression_summary.json').read_bytes()
    baseline = json.loads(raw)
    bid, ask, _, bars, _, _ = load_archive(root_2026)
    recent = measure(bid, ask, bars, START, END, baseline['historical_2026']['arms'])
    bid, ask, bars, _ = load_q4(root_q4)
    older = measure(bid, ask, bars, Q4_START, START, baseline['separate_2025_q4']['arms'])
    return dict(baseline_sha256=sha256(raw).hexdigest(),
                source_revision=baseline['source_revision'],
                historical_2026=recent, separate_2025_q4=older,
                diagnostic_allows_overlap=True, out_of_sample=False,
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
