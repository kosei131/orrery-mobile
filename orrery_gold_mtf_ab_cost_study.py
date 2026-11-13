# SPDX-License-Identifier: GPL-3.0-only
"""Sensitivity of pinned Gold A/B price references to flat round-trip friction."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from math import fsum
from pathlib import Path

from orrery_gold_mtf_ab_outcome_report import report
from orrery_gold_mtf_ab_price_references import VALID_FAMILIES

# USD of price per ounce. Scenarios are independent of the feed's quote basis.
COSTS = (0.0, 0.30, 0.54, 0.70)


def summarize(rows):
    resolved = [row for row in rows if row['reference_r'] is not None]
    stop_widths = [
        abs(float(row['entry_open_reference']) - float(row['structural_stop']))
        for row in resolved
    ]
    gross = [row['reference_r'] for row in resolved]
    unresolved_ids = [row['candidate_id'] for row in rows if row['reference_r'] is None]
    scenarios = []
    for cost in COSTS:
        adjusted = [value - cost / width for value, width in zip(gross, stop_widths)]
        wins = sum(value > 0 for value in adjusted)
        losses = -fsum(value for value in adjusted if value < 0)
        scenarios.append({
            'assumed_round_trip_cost_price': cost,
            'mean_cost_r': fsum(cost / width for width in stop_widths) / len(gross) if gross else None,
            'mean_adjusted_reference_r': fsum(adjusted) / len(gross) if gross else None,
            'positive_reference_pct': 100 * wins / len(gross) if gross else None,
            'unresolved_average_r_for_all_candidate_break_even': (
                -fsum(adjusted) / len(unresolved_ids) if unresolved_ids else None
            ),
            'adjusted_reference_pf': fsum(value for value in adjusted if value > 0) / losses if losses else None,
        })
    return {
        'candidates': len(rows),
        'resolved': len(resolved),
        'unresolved_ids': unresolved_ids,
        'break_even_flat_cost_price': fsum(gross) / fsum(1 / width for width in stop_widths) if gross else None,
        'scenarios': scenarios,
    }


def run(raw, bars_dir):
    original = report(raw, bars_dir)
    cohorts = {}
    for family in VALID_FAMILIES:
        rows = [row for row in original['records'] if row['family'] == family]
        months, hours = defaultdict(list), defaultdict(list)
        for row in rows:
            clock = datetime.fromtimestamp(row['known_at_utc'], timezone.utc)
            months[clock.strftime('%Y-%m')].append(row)
            hours[f'{clock.hour:02d}'].append(row)
        cohorts[family] = {
            'overall': summarize(rows),
            'by_signal_month_utc': {key: summarize(group) for key, group in sorted(months.items())},
            'by_signal_hour_utc': {key: summarize(group) for key, group in sorted(hours.items())},
        }
    return {
        'status': 'FIXED_OHLC_EXITS_HYPOTHETICAL_COST_SENSITIVITY',
        'raw_source_sha256': original['raw_source_sha256'],
        'bars_sha256': original['bars_sha256'],
        'cost_model': 'Subtract flat round-trip price friction divided by each indicative entry-to-stop width. Outcome sequence held fixed.',
        'cohorts': cohorts,
        'unresolved': [row for row in original['records'] if row['reference_r'] is None],
        'actual_win_rate_pct': None,
        'net_expectancy_r': None,
        'account_return_pct': None,
        'portfolio_drawdown': None,
        'out_of_sample': False,
        'execution_allowed': False,
        'adoption_allowed': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw_source', type=Path)
    parser.add_argument('bars_dir', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    payload = json.dumps(run(args.raw_source, args.bars_dir), indent=2, allow_nan=False)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(payload + '\n')
