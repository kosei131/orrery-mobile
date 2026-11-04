# SPDX-License-Identifier: GPL-3.0-only
"""Run causal three-family Gold M15 signals on pinned public OHLC bars.

These are publisher quote-basis-unverified candles, not broker Bid/Ask.
Source OHLC must remain unchanged; signals are NOT trade executions.
"""
import argparse
import csv
from datetime import datetime,timedelta
from decimal import Decimal,InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
from orrery_gold_three_hypotheses import scan

PIN='a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225'
SCALE=1000000


def run(raw, m15, *, expected_sha256=PIN):
    raw=Path(raw);m15=Path(m15)
    if not isinstance(expected_sha256,str) or len(expected_sha256)!=64:
        raise ValueError('Fixed raw source SHA256 required')
    actual=sha256(raw.read_bytes()).hexdigest()
    if actual!=expected_sha256:
        raise ValueError('Raw source pin mismatch')
    candles=[]
    with m15.open(newline='',encoding='utf-8') as f:
        reader=csv.DictReader(f)
        required={'timestamp_utc','bid_open','bid_high','bid_low','bid_close'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('Missing expected OHLC fields')
        for row in reader:
            dt=datetime.fromisoformat(row['timestamp_utc'])
            if dt.tzinfo is None or dt.utcoffset()!=timedelta(0):
                raise ValueError('Explicit UTC required')
            open_stamp=int(dt.timestamp())
            if open_stamp%900:raise ValueError('Unaligned M15 open')
            converted={}
            for col,key in (('bid_open','open'),('bid_high','high'),
                            ('bid_low','low'),('bid_close','close')):
                try:
                    v=Decimal(row[col])*SCALE
                except (InvalidOperation,TypeError):
                    raise ValueError('Invalid decimal OHLC')
                if not v.is_finite() or v!=v.to_integral_value():
                    raise ValueError('Prices require exact six-decimal scale')
                converted[key]=int(v)
            candles.append(dict(close_time=open_stamp+900,**converted))
    result=scan(candles)
    result['raw_source_sha256']=actual
    result['m15_sha256']=sha256(m15.read_bytes()).hexdigest()
    result['input_candles']=len(candles)
    result['price_scale']=SCALE
    result['quote_basis_verified']=False
    result['real_price_results_verified']=False
    result['no_bid_ask_spread_model']=True
    return result


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('raw_source')
    parser.add_argument('m15_csv')
    parser.add_argument('output')
    args=parser.parse_args(argv)
    output=Path(args.output)
    if output.exists() or output.is_symlink():
        parser.error('Output already exists')
    report=run(args.raw_source,args.m15_csv)
    with output.open('x',encoding='utf-8') as f:
        json.dump(report,f,indent=2,allow_nan=False)
    print(json.dumps(dict(input_candles=report['input_candles'],
                          signal_count_by_family=report['signal_count_by_family'])))


if __name__=='__main__':
    main()
