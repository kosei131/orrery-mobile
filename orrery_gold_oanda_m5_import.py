# SPDX-License-Identifier: GPL-3.0-only
"""Convert locally archived OANDA-style candle response pages to research input."""
import argparse
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import re

from orrery_gold_nested_wave_holdout import CONTEXT, END, START

FIELDS = ('o', 'h', 'l', 'c')


def normalize(pages, output_dir):
    if not 1 <= len(pages) <= 32:
        raise ValueError('Provide 1 to 32 archived response pages')
    rows, page_hashes = {}, []
    for path in pages:
        with path.open('rb') as source:
            raw = source.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError('Response page too large')
        page_hashes.append(sha256(raw).hexdigest())
        page = json.loads(raw)
        if (not isinstance(page, dict) or page.get('instrument') != 'XAU_USD'
                or page.get('granularity') != 'M5' or not isinstance(page.get('candles'), list)):
            raise ValueError('Expected XAU_USD M5 candle response')
        for candle in page['candles']:
            if (not isinstance(candle, dict) or candle.get('complete') is not True
                    or not isinstance(candle.get('mid'), dict)):
                raise ValueError('Confirmed MID candles required')
            clock = candle.get('time')
            if not isinstance(clock, str) or not re.fullmatch(
                    r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.0{1,9})?(?:Z|\+00:00)', clock):
                raise ValueError('Exact UTC candle start required')
            stamp = datetime.fromisoformat(clock.replace('Z', '+00:00'))
            epoch = int(stamp.timestamp())
            if epoch % 300 or not START - CONTEXT <= epoch < END or epoch in rows:
                raise ValueError('Off-grid, out-of-period or duplicate candle')
            prices = [candle['mid'].get(key) for key in FIELDS]
            if any(not isinstance(price, str) or not 1 <= len(price) <= 32 for price in prices):
                raise ValueError('Bounded decimal price strings required')
            try:
                o, h, l, c = (Decimal(price) for price in prices)
            except InvalidOperation as exc:
                raise ValueError('Invalid MID OHLC') from exc
            if (not all(p.is_finite() and Decimal('0.000001') <= p <= 1000000 for p in (o,h,l,c))
                    or not l <= min(o,c) <= max(o,c) <= h):
                raise ValueError('Invalid MID OHLC')
            rows[epoch] = [stamp.isoformat(), *prices]
    if not any(START <= stamp < END-300 for stamp in rows):
        raise ValueError('No usable M5 candles in evaluation window')

    output_dir.mkdir()
    csv_path = output_dir / 'xauusd_m5_mid.csv'
    with csv_path.open('x', encoding='utf-8', newline='') as target:
        writer = csv.writer(target, lineterminator='\n')
        writer.writerow(('timestamp_utc', 'bid_open', 'bid_high', 'bid_low', 'bid_close'))
        writer.writerows(rows[stamp] for stamp in sorted(rows))
    digest = sha256(csv_path.read_bytes()).hexdigest()
    receipt = dict(instrument='OANDA:XAUUSD', timeframe='M5', price_basis='MID',
                   timestamp_convention='UTC_BAR_OPEN', confirmed_only=True, csv_sha256=digest,
                   acquisition_reference='Locally archived response pages; SHA256 in source_page_sha256',
                   source_page_sha256=page_hashes, independent_source_authentication=False)
    with (output_dir / 'source_receipt.json').open('x', encoding='utf-8') as target:
        json.dump(receipt, target, indent=2)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output_dir', type=Path)
    parser.add_argument('pages', nargs='+', type=Path)
    args = parser.parse_args()
    print(normalize(args.pages, args.output_dir)['csv_sha256'])
