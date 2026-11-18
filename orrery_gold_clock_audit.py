# SPDX-License-Identifier: GPL-3.0-only
"""Compare pinned Gold minute coverage with the published NY session hypothesis."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from orrery_gold_ab_archive_comparison import aggregate_complete
from orrery_gold_hourly_trend import longest_chain
from orrery_gold_nested_wave_october import complete_m5
from orrery_gold_pullback_study import START, END, load_archive
from orrery_gold_session_breakout import Q4_START, load_q4

NY = ZoneInfo('America/New_York')


def scheduled_open(stamp):
    local = datetime.fromtimestamp(stamp, timezone.utc).astimezone(NY)
    weekday, hour = local.weekday(), local.hour
    if weekday == 5:
        return False
    if weekday == 6:
        return hour >= 18
    if weekday == 4:
        return hour < 17
    return hour < 17 or hour >= 18


def inherited_chain(bars, seconds, start, open_prefix):
    current = longest = permitted = blocked = 0
    previous = None
    for row in bars:
        end = row['close_time']
        begin = end-seconds
        a, b = (begin-start)//60, (end-start)//60
        if open_prefix[b]-open_prefix[a] != seconds//60:
            continue
        if previous is None:
            current = 1
        else:
            left = (previous-start)//60
            missing_open = open_prefix[a]-open_prefix[left]
            if missing_open:
                blocked += 1
                current = 1
            else:
                current += 1
                permitted += begin > previous
        longest = max(longest, current)
        previous = end
    return dict(longest_chain=longest, closed_gap_carries=permitted, open_gap_resets=blocked)


def audit(bid, ask, start, end):
    shared = bid.keys() & ask.keys()
    counts = Counter()
    prefix = [0]
    h4 = {}
    for t in range(start, end, 60):
        is_open = scheduled_open(t)
        present = t in shared
        counts[('present_' if present else 'missing_')+('open' if is_open else 'closed')] += 1
        prefix.append(prefix[-1]+is_open)
        slot = t-t%14400
        state = h4.setdefault(slot, Counter())
        state['scheduled_open'] += is_open
        state['observed_open'] += is_open and present
    classes = Counter()
    for value in h4.values():
        expected, observed = value['scheduled_open'], value['observed_open']
        if not expected:
            classes['no_scheduled_open_minutes'] += 1
        elif expected == 240 and observed == 240:
            classes['complete_standard_h4'] += 1
        elif expected < 240 and observed == expected:
            classes['complete_partial_session_h4'] += 1
        else:
            classes['missing_scheduled_open_minutes'] += 1
    m5 = complete_m5({t: bid[t] for t in shared}, start, end)
    bars = {}
    for name, seconds in (('H1',3600),('H4',14400)):
        frame = aggregate_complete(m5, seconds)
        bars[name] = dict(strict_longest=longest_chain(frame, seconds),
                          session_hypothesis=inherited_chain(frame, seconds, start, prefix))
    return dict(minutes=dict(counts), utc_h4_classes=dict(classes), continuity=bars)


def run(current_root, prior_root):
    bid, ask, _, _, _, _ = load_archive(current_root)
    recent = audit(bid, ask, START, END)
    bid, ask, _, _ = load_q4(prior_root)
    old = audit(bid, ask, Q4_START, START)
    return dict(historical_2026=recent, separate_2025_q4=old,
                session_rule='America/New_York Sun 18:00 through Fri 17:00 with daily 17:00-18:00 break',
                historical_holiday_exceptions_authenticated=False,
                historical_session_rule_authenticated=False,
                prices_interpolated=False, profits_evaluated=False,
                execution_allowed=False, adoption_allowed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_2026', type=Path)
    parser.add_argument('archive_2025_q4', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        json.dump(run(args.archive_2026, args.archive_2025_q4), output, indent=2, allow_nan=False)
        output.write('\n')
