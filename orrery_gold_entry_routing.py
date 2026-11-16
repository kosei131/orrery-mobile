# SPDX-License-Identifier: GPL-3.0-only
"""Fixed Gold entry routing on the previously unused Q2 2025 archive."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha1
import json
from pathlib import Path
from statistics import mean
import sys

from orrery_gold_ab_archive_comparison import aggregate_complete
from orrery_gold_conditional_exit import COST, RESOLVED, stats
from orrery_gold_entry_friction_study import MAX_COST_SHARE, MIN_BREAKOUT, entry_features
from orrery_gold_expectancy_study import retarget
from orrery_gold_level_retest import NO_TRADE, TARGET_R, score, wait_for_retest
from orrery_gold_nested_wave_october import complete_m5
from orrery_gold_probability_study import candidates
from orrery_gold_pullback_study import suspect_flat_minutes
from orrery_paired_archive_study import REVISION, read_side

START, END = (int(datetime(2025, month, 1, tzinfo=timezone.utc).timestamp())
              for month in (4, 7))
PINS = {
    'bid': ('aff4975ce8522f28951940db2daff3f36d5b3155',
            '6470db6ad153edb9bffd41660d0ae9b4370e4662',
            'b21e4764f19340da04b524f228264ff907d818f0'),
    'ask': ('a7a1b04849f88708aea270fd5ba09588bc7b435a',
            '757914bda7c25b568976f55fca615e180d3e75a4',
            '06a264ccf5b942c8c3a371956fd2ff0c31b219c'),
}
SKIP = 'ROUTER_SKIP_FRICTION'


def load(root):
    sides = {}
    audits = {}
    for side, pins in PINS.items():
        rows = {}
        for month, pin in zip(range(4, 7), pins):
            name = f'{side}_2025_{month:02}.csv'
            path = root/name
            if path.stat().st_size > 20*1024*1024:
                raise ValueError(f'Oversize archive {name}')
            raw = path.read_bytes()
            if sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest() != pin:
                raise ValueError(f'Pinned Git blob mismatch: {name}')
            new, audits[name] = read_side(path)
            if rows.keys() & new.keys() or any(
                (d.year, d.month) != (2025, month)
                for d in (datetime.fromtimestamp(t, timezone.utc) for t in new)
            ):
                raise ValueError(f'Unexpected archive timestamps: {name}')
            rows.update(new)
        sides[side] = rows
    bid, ask = sides['bid'], sides['ask']
    shared = bid.keys() & ask.keys()
    if any(ask[t][k] < bid[t][k] for t in shared for k in ('open', 'high', 'low', 'close')):
        raise ValueError('Crossed quotes')
    before = len(shared)
    for t in set(suspect_flat_minutes(bid)) | set(suspect_flat_minutes(ask)):
        bid.pop(t, None)
        ask.pop(t, None)
    shared = bid.keys() & ask.keys()
    m5 = complete_m5({t: bid[t] for t in shared}, START, END)
    return bid, ask, m5, dict(paired_minutes=len(shared), removed_flat_minutes=before-len(shared),
                             sha256={k: a['sha256'] for k, a in audits.items()})


def dispositions(rows):
    trade_rows = [r for r in rows if r['status'] not in NO_TRADE | {SKIP}]
    result = stats(trade_rows)
    return dict(summary=result, statuses=dict(Counter(r['status'] for r in rows)),
                resolved_per_week=result['resolved']*604800/(END-START))


def run(root):
    bid, ask, m5, audit = load(root)
    m15 = aggregate_complete(m5, 900)
    clocks = {row['close_time']: row for row in m15}
    m5_by_close = {row['close_time']: row for row in m5}
    actions = Counter()
    comparisons = []
    for row in candidates(bid, ask, m15, END):
        at = row['at_utc']
        immediate = retarget(row, bid, ask, TARGET_R)
        features = entry_features(row, clocks, bid, ask, TARGET_R)
        if features is None or immediate['status'] == 'STOP_INVALID_AT_ENTRY':
            waiting = dict(status=(immediate['status'] if immediate['status'] != RESOLVED
                                   else 'UNKNOWN_ENTRY_FEATURES'))
            action, routed = 'UNAVAILABLE', waiting
        else:
            buy = row['side'] == 'BUY'
            prior = [clocks[t] for t in range(at-3600, at, 900)]
            level = max(x['high'] for x in prior) if buy else min(x['low'] for x in prior)
            entry = (ask if buy else bid)[at]['open']
            target = entry+TARGET_R*(entry-row['stop'])
            waiting = wait_for_retest(row, level, target, m5_by_close, bid, ask)
            cost, strength = features
            if cost > MAX_COST_SHARE:
                action, routed = 'SKIP', dict(status=SKIP)
            elif strength >= MIN_BREAKOUT:
                action, routed = 'IMMEDIATE', immediate
            else:
                action, routed = 'WAIT', waiting
        actions[action] += 1
        comparisons.append((immediate, waiting, routed))
    values = [tuple(0.0 if r['status'] == SKIP else score(r) for r in group) for group in comparisons]
    common = [row for row in values if all(v is not None for v in row)]
    arms = ('immediate', 'wait', 'routed')
    return dict(
        study='gold_entry_routing_q2', source_revision=REVISION, audit=audit, actions=dict(actions),
        period='2025-04-01 through 2025-07-01 exclusive UTC', base_candidates=len(comparisons),
        common_candidates=len(common), unknown_candidates=len(values)-len(common),
        arms={k: dispositions([r[i] for r in comparisons]) for i,k in enumerate(arms)},
        common_mean_r={k: mean(r[i] for r in common) if common else None for i,k in enumerate(arms)},
        extra_round_trip_price=COST, target_r_at_breakout=TARGET_R,
        execution_allowed=False, adoption_allowed=False, account_return_pct=None,
    )


if __name__ == '__main__':
    print(json.dumps(run(Path(sys.argv[1])), separators=(',', ':'), allow_nan=False))
