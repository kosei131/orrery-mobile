# SPDX-License-Identifier: GPL-3.0-only
"""Audit M1 Bid exit ordering for the existing paired Gold candidate set."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
from statistics import mean, median

from orrery_gold_nested_wave_october import END, SOURCE, read_pinned
from orrery_gold_nested_wave_paired import run as paired_replay
from orrery_gold_nested_wave_study import summarize


def minute_exit(record, bid, *, end):
    """Keep the Ask entry and bracket fixed, then inspect each completed M1."""
    result = dict(record, reference_r=None, exit_m5_close=None, exit_m1_close=None)
    if any(record[key] is None for key in ('entry_open_reference', 'target_reference')):
        return result
    if record['state'] in ('CENSORED_INVALID_OPEN_RISK', 'CENSORED_NO_TARGET_ROOM_AT_OPEN'):
        return result
    entry, stop, target = (Decimal(record[key]) for key in
                           ('entry_open_reference', 'structural_stop', 'target_reference'))
    start = record['known_at_utc']
    for stamp in range(start, start + 7200, 60):
        if stamp + 60 >= end:
            return dict(result, state='CENSORED_PERIOD_END_M1')
        if stamp not in bid:
            return dict(result, state='CENSORED_M1_GAP')
        row = bid[stamp]
        opening, high, low, close = (Decimal(str(row[key])) for key in
                                     ('open', 'high', 'low', 'close'))
        price = None
        if opening <= stop:
            state, price = 'ADVERSE_OPEN_REFERENCE', opening
        elif opening >= target:
            state, price = 'FAVORABLE_OPEN_CAPPED_REFERENCE', target
        elif low <= stop and high >= target:
            return dict(result, state='AMBIGUOUS_SAME_M1', exit_m1_close=stamp + 60)
        elif low <= stop:
            state, price = 'STOP_REFERENCE', stop
        elif high >= target:
            state, price = 'TARGET_REFERENCE', target
        elif stamp + 60 == start + 7200:
            state, price = 'TIMEOUT_REFERENCE', close
        if price is not None:
            return dict(result, state=state, exit_m1_close=stamp + 60,
                        reference_r=float((price-entry)/(entry-stop)))
    raise AssertionError('M1 exit horizon must terminate')


def audit_payoff(records, bid):
    rows = []
    for record in records:
        if record['reference_r'] is None:
            continue
        entry, stop, target = (Decimal(record[key]) for key in
                               ('entry_open_reference', 'structural_stop', 'target_reference'))
        risk = entry - stop
        before_exit = range(record['known_at_utc'], record['exit_m1_close'] - 60, 60)
        highs = [Decimal(str(bid[stamp]['high'])) for stamp in before_exit]
        best = max(highs, default=None)
        rows.append(dict(
            candidate_id=record['candidate_id'], target_r=float((target - entry) / risk),
            risk_price=float(risk), realized_reference_r=record['reference_r'],
            observed_pre_exit_minutes=len(highs),
            best_bid_move_before_exit_bar_r=float((best - entry) / risk) if best is not None else None,
        ))
    targets = [row['target_r'] for row in rows]
    positive = [row['realized_reference_r'] for row in rows if row['realized_reference_r'] > 0]
    negative = [row['realized_reference_r'] for row in rows if row['realized_reference_r'] < 0]
    return dict(resolved=len(rows), target_below_one_r=sum(value < 1 for value in targets),
                median_target_r=median(targets) if targets else None,
                mean_positive_reference_r=mean(positive) if positive else None,
                mean_negative_reference_r=mean(negative) if negative else None,
                records=rows)



def audit_early_progress(records, bid, *, end):
    """Measure at fixed landmarks, carrying forward exits already observed."""
    reports = []
    for minutes in (5, 15, 30):
        rows = []
        for record in records:
            start = record['known_at_utc']
            cutoff = start + minutes * 60
            exit_at = record['exit_m1_close']
            entry = record['entry_open_reference']
            value = None
            if (entry is None or record['target_reference'] is None
                    or record['state'] == 'CENSORED_NO_TARGET_ROOM_AT_OPEN'):
                status = 'NO_VALID_ENTRY'
            elif exit_at is not None and exit_at <= cutoff:
                value = record['reference_r']
                status = 'EXITED' if value is not None else 'AMBIGUOUS_EXIT'
            elif cutoff >= end or any(t not in bid for t in range(start, cutoff, 60)):
                status = 'UNKNOWN_PATH'
            else:
                mark = Decimal(str(bid[cutoff-60]['close']))
                entry_price = Decimal(entry)
                risk = entry_price - Decimal(record['structural_stop'])
                value = float((mark-entry_price)/risk)
                status = 'OPEN_AT_LANDMARK'
            rows.append(dict(candidate_id=record['candidate_id'], status=status, reference_r=value))
        values = [row['reference_r'] for row in rows if row['reference_r'] is not None]
        reports.append(dict(minutes=minutes, observed=len(values), unknown=len(rows)-len(values),
                            exited=sum(row['status']=='EXITED' for row in rows),
                            positive=sum(value > 0 for value in values),
                            median_reference_r=median(values) if values else None, records=rows))
    return reports



def audit_early_exit(records, progress, bid, *, end):
    """Compare a single below-entry check per arm, at the next observed open."""
    baseline = {row['candidate_id']: row for row in records}
    scenarios = []
    for landmark in progress:
        minutes = landmark['minutes']
        updated, changes = [], []
        for mark in landmark['records']:
            original = baseline[mark['candidate_id']]
            if mark['status'] != 'OPEN_AT_LANDMARK' or mark['reference_r'] >= 0:
                updated.append(original)
                continue
            stamp = original['known_at_utc'] + minutes * 60
            if stamp not in bid or stamp + 60 >= end:
                alternative = dict(original, state='CENSORED_EARLY_EXIT_OPEN',
                                   reference_r=None)
            else:
                entry = Decimal(original['entry_open_reference'])
                stop = Decimal(original['structural_stop'])
                target = Decimal(original['target_reference'])
                # An existing TP still caps a favorable opening gap.
                opening = min(Decimal(str(bid[stamp]['open'])), target)
                alternative = dict(original, state='EARLY_EXIT_BID_OPEN_REFERENCE',
                                   reference_r=float((opening-entry)/(entry-stop)))
            updated.append(alternative)
            changes.append(dict(candidate_id=mark['candidate_id'], decision_at_utc=stamp,
                                baseline_r=original['reference_r'],
                                early_exit_r=alternative['reference_r']))
        comparable = [row for row in changes
                      if row['baseline_r'] is not None and row['early_exit_r'] is not None]
        scenarios.append(dict(
            minutes=minutes, summary=summarize(updated), triggered=len(changes),
            comparable_triggers=len(comparable),
            improved=sum(row['early_exit_r'] > row['baseline_r'] for row in comparable),
            worsened=sum(row['early_exit_r'] < row['baseline_r'] for row in comparable),
            baseline_winners_reduced=sum(row['baseline_r'] > 0 and row['early_exit_r'] < row['baseline_r']
                                        for row in comparable),
            changes=changes,
        ))
    return scenarios



def run(root):
    paired = paired_replay(root)
    sep, _ = read_pinned(root / 'bid_2026_09.csv', 'bid_2026_09.csv')
    oct_, _ = read_pinned(root / SOURCE, SOURCE)
    bid = sep | oct_
    reports = {}
    for arm in ('immediate', 'delayed', 'delayed_with_room_gate'):
        previous = paired['paired'][arm]['records']
        minute = [minute_exit(record, bid, end=END) for record in previous]
        progress = audit_early_progress(minute, bid, end=END)
        reports[arm] = dict(
            previous_m5=paired['paired'][arm]['summary'],
            minute=summarize(minute),
            payoff_audit=audit_payoff(minute, bid),
            early_progress=progress,
            early_exit_sensitivity=audit_early_exit(minute, progress, bid, end=END),
            comparisons=[dict(candidate_id=a['candidate_id'], m5_state=a['state'],
                              m5_reference_r=a['reference_r'], m5_close=a['exit_m5_close'],
                              m1_state=b['state'],
                              m1_reference_r=b['reference_r'], m1_close=b['exit_m1_close'])
                         for a, b in zip(previous, minute, strict=True)],
        )
    return dict(status='THIRD_PARTY_M1_EXIT_ORDER_AUDIT',
                source_audits=paired['source_audits'], arms=reports,
                actual_broker_profit=None, execution_allowed=False, adoption_allowed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_directory', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    payload = json.dumps(run(args.archive_directory), indent=2, allow_nan=False)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(payload + '\n')
