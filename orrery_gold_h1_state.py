# SPDX-License-Identifier: GPL-3.0-only
"""Causal features on unchanged Gold H1 entries; retrospective attribution only."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite, sqrt
from pathlib import Path

from lsr03_vhf import calculate as vhf
from orrery_gold_ab_archive_comparison import aggregate_complete
from orrery_gold_channel_breakout import summarize
from orrery_gold_clock_audit import NY
from orrery_gold_nested_wave_october import complete_m5
from orrery_gold_pullback_study import START, END, load_archive
from orrery_gold_session_breakout import Q4_START, load_q4
from orrery_gold_session_hourly import chains, measure

EVIDENCE = Path(__file__).with_name('research_evidence') / 'local-history-20261101'
COST = .30
FAMILIES = {
    'vhf14': ('HIGH_RISING', 'HIGH_NOT_RISING', 'LOW_RISING', 'LOW_NOT_RISING'),
    'net20': ('ALIGNED', 'OPPOSED', 'FLAT'),
    'efficiency20': ('BELOW_030', 'AT_LEAST_030'),
    'friction_r': ('AT_MOST_002', '002_TO_005', 'ABOVE_005', 'UNKNOWN'),
    'side': ('BUY', 'SELL'),
    'ny_clock': ('00_07', '08_12', '13_16', '18_23', 'CLOSED'),
}


def features(window, signal, bid_open, ask_open):
    at = signal['at_utc']
    if (len(window) != 21 or window[-1]['close_time'] != at
            or any(r['close_time'] > at for r in window)
            or any(a['close_time'] >= b['close_time'] for a,b in zip(window, window[1:]))):
        raise ValueError('Feature window must end at the confirmed signal')
    side = signal['side']
    if side not in ('BUY', 'SELL') or signal['stop_distance'] <= 0:
        raise ValueError('Invalid signal')
    closes = [r['close'] for r in window]
    change = closes[-1]-closes[0]
    travel = sum(abs(b-a) for a,b in zip(closes,closes[1:]))
    efficiency = abs(change)/travel if travel else 0.0
    signed = (1 if side == 'BUY' else -1)*change
    indicator = vhf(window, period=14)
    if indicator['status'] != 'OK':
        raise ValueError('VHF history missing')
    strength = 'HIGH' if indicator['value'] >= .4 else 'LOW'
    rising = 'RISING' if indicator['slope'] == 'RISING' else 'NOT_RISING'
    friction = None
    if bid_open is not None and ask_open is not None:
        if not all(isfinite(p) and p > 0 for p in (bid_open, ask_open)) or ask_open < bid_open:
            raise ValueError('Invalid entry quote')
        spread = ask_open-bid_open
        friction = (spread+COST)/(signal['stop_distance']+spread)
    cost_group = ('UNKNOWN' if friction is None else 'AT_MOST_002' if friction <= .02
                  else '002_TO_005' if friction <= .05 else 'ABOVE_005')
    hour = datetime.fromtimestamp(at,timezone.utc).astimezone(NY).hour
    clock = '00_07' if hour < 8 else '08_12' if hour < 13 else '13_16' if hour < 17 else 'CLOSED' if hour == 17 else '18_23'
    return dict(at_utc=at, known_at_utc=at, side=side, vhf14_value=indicator['value'],
        vhf14_slope=indicator['slope'], efficiency20_value=efficiency,
        estimated_entry_friction_r=friction,
        groups=dict(vhf14=strength+'_'+rising, net20='ALIGNED' if signed>0 else 'OPPOSED' if signed<0 else 'FLAT',
            efficiency20='AT_LEAST_030' if efficiency>=.3 else 'BELOW_030',
            friction_r=cost_group, side=side, ny_clock=clock))


def describe(rows):
    output = summarize(rows)
    resolved = [r for r in rows if r['status']=='RESOLVED_REFERENCE']
    gross = sum(r['r'] for r in resolved)
    cost = sum(COST/r['initial_risk_price'] for r in resolved)
    net = gross-cost
    wins = sum(r['r']-COST/r['initial_risk_price'] > 0 for r in resolved)
    n = len(resolved)
    # Wilson descriptive binomial interval; trades may be dependent.
    interval = None
    if n:
        z = 1.959963984540054
        p = wins/n
        center = (p+z*z/(2*n))/(1+z*z/n)
        half = z*sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
        interval = [max(0,center-half), min(1,center+half)]
    output.update(gross_total_resolved_r=gross, extra_cost_total_resolved_r=cost,
        net_total_resolved_r=net, net_mean_all_candidates_r=None if len(rows)!=n else net/n if n else None,
        descriptive_win_fraction_wilson95=interval,
        by_exit_reason={reason:dict(count=len(items),net_total_r=sum(r['r']-COST/r['initial_risk_price'] for r in items))
            for reason in sorted({r['exit_reason'] for r in resolved})
            for items in [[r for r in resolved if r['exit_reason']==reason]]})
    return output


def attribute(rows, feature_by_clock):
    annotated = []
    for row in rows:
        f = feature_by_clock.get(row['at_utc'])
        if f is None or f['side'] != row['side']:
            raise ValueError('Entry and causal features disagree')
        annotated.append(dict(row, features=f))
    if len({r['at_utc'] for r in annotated}) != len(annotated):
        raise ValueError('Duplicate baseline entry')
    groups = {}
    for family, names in FAMILIES.items():
        buckets = {name:[] for name in names}
        for row in annotated:
            buckets[row['features']['groups'][family]].append(row)
        months = sorted({datetime.fromtimestamp(r['at_utc'],timezone.utc).strftime('%Y-%m') for r in rows})
        groups[family] = {name:dict(describe(items), by_utc_month={month:describe([r for r in items if
            datetime.fromtimestamp(r['at_utc'],timezone.utc).strftime('%Y-%m')==month]) for month in months})
            for name,items in buckets.items()}
        if sum(g['candidates'] for g in groups[family].values()) != len(rows):
            raise ValueError('Incomplete family partition')
    return dict(overall=describe(rows), groups=groups, annotated_records=annotated,
                filtered_strategy_replayed=False)


def period(bid, ask, m5, start, end, expected):
    reproduced = measure(bid, ask, m5, start, end)
    if reproduced != expected:
        raise ValueError('Pinned baseline did not reproduce')
    baseline = expected['records']['SESSION_HYPOTHESIS']
    signals = {r['at_utc']:r for r in baseline}
    h1 = aggregate_complete(m5,3600)
    causal = {}
    for window in chains(h1,session=True):
        at = window[-1]['close_time']
        if at in signals:
            causal[at] = features(window, signals[at],
                bid[at]['open'] if at in bid else None,
                ask[at]['open'] if at in ask else None)
    return dict(start_utc=expected['start_utc'], end_utc_exclusive=expected['end_utc_exclusive'],
                baseline_reproduced=True, **attribute(baseline,causal))


def run(root, prior_root):
    plan_bytes=(EVIDENCE/'gold_h1_state_plan.json').read_bytes()
    plan=json.loads(plan_bytes)
    for filename, expected in plan['files_sha256'].items():
        if sha256(Path(__file__).parent.joinpath(filename).read_bytes()).hexdigest()!=expected:
            raise ValueError('Diagnostic code/input pin mismatch: '+filename)
    raw = (EVIDENCE/'gold_session_hourly_results.json').read_bytes()
    baseline = json.loads(raw)
    bid, ask, m5, _, _, _ = load_archive(root)
    recent = period(bid,ask,m5,START,END,baseline['historical_2026'])
    bid, ask, _, _ = load_q4(prior_root)
    m5 = complete_m5({t:bid[t] for t in bid.keys() & ask.keys()},Q4_START,START)
    older = period(bid,ask,m5,Q4_START,START,baseline['separate_2025_q4'])
    return dict(study='gold_h1_state_v1', historical_2026=recent, separate_2025_q4=older,
        baseline_sha256=sha256(raw).hexdigest(), plan_sha256=sha256(plan_bytes).hexdigest(),
        group_families=len(FAMILIES), groups_per_period=sum(map(len,FAMILIES.values())),
        extra_cost_price=COST, retrospective=True, out_of_sample=False,
        filtered_strategy_replayed=False, account_return_pct=None, account_max_dd_pct=None,
        historical_session_rule_authenticated=False, execution_allowed=False, adoption_allowed=False)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_2026',type=Path)
    parser.add_argument('archive_2025_q4',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    result=run(args.archive_2026,args.archive_2025_q4)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(result,stream,indent=2,allow_nan=False)
        stream.write('\n')
