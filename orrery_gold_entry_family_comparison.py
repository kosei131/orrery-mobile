# SPDX-License-Identifier: GPL-3.0-only
"""Compare frozen Gold entry families on one historical price reference."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from orrery_gold_mtf_ab_price_references import VALID_FAMILIES, evaluate
from orrery_gold_mtf_ab_replay import run as scan_ab
from orrery_gold_nested_wave_early_exit_public import END, START
from orrery_gold_nested_wave_holdout import replay_window
from orrery_gold_nested_wave_study import summarize
from orrery_real_bars_lsr_bridge import load


def describe(rows):
    return dict(
        all=summarize(rows),
        buy=summarize([row for row in rows if row['side'] == 'BUY']),
        sell=summarize([row for row in rows if row['side'] == 'SELL']),
        candidate_ids=[row['candidate_id'] for row in rows],
    )


def compare_period(all_m5, ab_candidates, start, end):
    wave = replay_window(all_m5, start=start, end=end)
    m5 = [{key: value for key, value in row.items() if key != 'open_time'}
          for row in all_m5 if start <= row['open_time'] and row['close_time'] < end]
    selected = [row for row in ab_candidates if start <= row['known_at_utc'] < end]
    outcomes = evaluate(m5, selected)['records']
    wave_rows = wave['immediate']['records']
    families = {name: describe([row for row in outcomes if row['family'] == name])
                for name in VALID_FAMILIES}
    families['NESTED_WAVE_IMMEDIATE'] = describe(wave_rows)
    overlap = sorted({row['known_at_utc'] for row in outcomes if row['side'] == 'BUY'}
                     & {row['known_at_utc'] for row in wave_rows})
    return dict(start_utc=datetime.fromtimestamp(start, timezone.utc).isoformat(),
                end_utc_exclusive=datetime.fromtimestamp(end, timezone.utc).isoformat(),
                observed_m5=len(m5), families=families, shared_buy_signal_clocks=overlap)


def run(source, bars_dir):
    ab = scan_ab(source, bars_dir)
    m5_path = bars_dir / 'XAUUSD_M5_UNVERIFIED_QUOTE.csv'
    all_m5 = load(m5_path, 'M5')['bars']
    if sha256(m5_path.read_bytes()).hexdigest() != ab['bars_sha256']['M5']:
        raise ValueError('M5 source changed after candidate scan')
    september_end = int(datetime(2026, 9, 26, tzinfo=timezone.utc).timestamp())
    return dict(
        status='EXPLORATORY_GOLD_ENTRY_FAMILY_COMPARISON',
        source_sha256=ab['raw_source_sha256'], bars_sha256=ab['bars_sha256'],
        pre_september=compare_period(all_m5, ab['candidates'], START, END),
        september=compare_period(all_m5, ab['candidates'], END, september_end),
        assumptions='Common M5 entry and exit evaluator, 120-minute maximum, fixed friction scenarios. Structural stops and target ceilings follow each strategy.',
        price_basis='publisher OHLC; quote side unverified',
        out_of_sample=False, actual_broker_profit=None,
        execution_allowed=False, adoption_allowed=False,
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('public_m1', 'bars_dir', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    payload = json.dumps(run(args.public_m1, args.bars_dir), indent=2, allow_nan=False)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(payload + '\n')
