# SPDX-License-Identifier: GPL-3.0-only
"""Pinned public XAU M15 price-reference comparison for three hypotheses.

Double-read the same M15 file with a hash check; do not mistake unverified
publisher OHLC for broker Bid/Ask or historical executable PnL.
"""
import argparse
import csv
from datetime import datetime,timedelta
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from orrery_gold_three_hypotheses_public import run as candidates_from_public, SCALE
from orrery_gold_m15_reference_outcomes import measure


def compare(raw,m15):
    report=candidates_from_public(raw,m15)
    m15=Path(m15)
    before=report['m15_sha256']
    bars=[]
    with m15.open(newline='',encoding='utf-8') as f:
        for row in csv.DictReader(f):
            t=datetime.fromisoformat(row['timestamp_utc'])
            if t.tzinfo is None or t.utcoffset()!=timedelta(0) or t.second or t.microsecond:
                raise ValueError('UTC M15 timestamp required')
            b={'close_time':int(t.timestamp())+900}
            for name in ('open','high','low','close'):
                scaled=Decimal(row['bid_'+name])*SCALE
                if not scaled.is_finite() or abs(scaled-scaled.to_integral_value())>Decimal('0.001'):
                    raise ValueError('Six-decimal normalization tolerance exceeded')
                b[name]=int(scaled.to_integral_value())
            bars.append(b)
    if sha256(m15.read_bytes()).hexdigest()!=before or len(bars)!=report['input_candles']:
        raise ValueError('M15 input changed during comparison')
    result=measure(bars,report['signals'])
    result['raw_source_sha256']=report['raw_source_sha256']
    result['m15_sha256']=before
    result['input_m15_bars']=len(bars)
    result['signal_count_by_family']=report['signal_count_by_family']
    result['sample_reused_for_hypothesis_design']=True
    result['real_broker_bid_ask_available']=False
    result['out_of_sample']=False
    return result


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('raw_source')
    p.add_argument('m15_csv')
    p.add_argument('output')
    args=p.parse_args(argv)
    target=Path(args.output)
    if target.exists() or target.is_symlink():
        p.error('Refusing to overwrite')
    d=compare(args.raw_source,args.m15_csv)
    with target.open('x',encoding='utf-8') as f:
        json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps(dict(cohorts=d['cohorts'],net_expectancy_r=d['net_expectancy_r']),allow_nan=False))


if __name__=='__main__':
    main()
