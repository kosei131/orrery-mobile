# SPDX-License-Identifier: GPL-3.0-only
"""Apply existing early exits to the pre-September public XAUUSD price sample."""
import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from orrery_gold_mtf_ab_replay import BARS_PINS, RAW_PIN
from orrery_gold_nested_wave_holdout import replay_window
from orrery_gold_nested_wave_minute import audit_early_exit, audit_early_progress, minute_exit
from orrery_gold_nested_wave_study import summarize
from orrery_public_xau_to_bars import run as convert
from orrery_real_bars_lsr_bridge import load

START = int(datetime(2026, 3, 26, tzinfo=timezone.utc).timestamp())
END = int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp())


def run(source):
    if sha256(source.read_bytes()).hexdigest() != RAW_PIN:
        raise ValueError('Public source pin mismatch')
    with TemporaryDirectory() as directory:
        root = Path(directory)
        convert(source, root)
        m5 = root / 'XAUUSD_M5_UNVERIFIED_QUOTE.csv'
        if sha256(m5.read_bytes()).hexdigest() != BARS_PINS['M5']:
            raise ValueError('Derived M5 pin mismatch')
        replay = replay_window(load(m5, 'M5')['bars'], start=START, end=END)
        with (root / 'XAUUSD_M1_UNVERIFIED_QUOTE.csv').open(newline='', encoding='utf-8') as file:
            minute_prices = {
                int(datetime.fromisoformat(row['timestamp_utc']).timestamp()):
                {key: row[f'bid_{key}'] for key in ('open', 'high', 'low', 'close')}
                for row in csv.DictReader(file)
            }
    if sha256(source.read_bytes()).hexdigest() != RAW_PIN:
        raise ValueError('Public source changed during replay')
    plans = replay['immediate']['records']
    minutes = [minute_exit(plan, minute_prices, end=END) for plan in plans]
    progress = audit_early_progress(minutes, minute_prices, end=END)
    return dict(
        status='EXPLORATORY_PUBLIC_XAU_EARLY_EXIT_PRE_SEPTEMBER',
        start_utc_epoch=START, end_utc_epoch=END, source_sha256=RAW_PIN,
        m5_sha256=BARS_PINS['M5'], observed_m5=replay['observed_m5'],
        price_basis='publisher OHLC; quote side unverified',
        rule='below the reference entry at a completed landmark; next observed M1 open',
        cost_model='hypothetical flat friction for scoring; trigger uses publisher price',
        original_m5=replay['immediate']['summary'],
        baseline_m1=summarize(minutes),
        early_exit_sensitivity=audit_early_exit(minutes, progress, minute_prices, end=END),
        out_of_sample=False, actual_broker_profit=None,
        execution_allowed=False, adoption_allowed=False,
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('public_m1', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    payload = json.dumps(run(args.public_m1), indent=2, allow_nan=False)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(payload + '\n')
