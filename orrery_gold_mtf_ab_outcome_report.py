# SPDX-License-Identifier: GPL-3.0-only
"""Pinned public XAU MTF A/B outcome report. Not actual trades.

Recompute candidates from original SHA256-pinned H4/M15/M5 and apply
hypothetical next-M5-open and structure/target barrier references.
Never treat unknown quote basis or fills as realized PnL.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from orrery_gold_mtf_ab_replay import run as scan, BARS_PINS
from orrery_real_bars_lsr_bridge import load
from orrery_gold_mtf_ab_price_references import evaluate


def report(raw,bars_dir):
    candidate_report=scan(raw,bars_dir)
    path=Path(bars_dir)/'XAUUSD_M5_UNVERIFIED_QUOTE.csv'
    if sha256(path.read_bytes()).hexdigest()!=BARS_PINS['M5']:
        raise ValueError('M5 source drift between scan and outcome analysis')
    bars=[]
    for b in load(path,'M5')['bars']:
        if set(b)!={'open_time','close_time','open','high','low','close'} or b['open_time']+300!=b['close_time']:
            raise ValueError('Unverified M5 input schema')
        bars.append({k:b[k] for k in ('close_time','open','high','low','close')})
    results=evaluate(bars,candidate_report['candidates'])
    if any(results['cohorts'][family]['candidates']!=n
           for family,n in candidate_report['candidate_counts'].items()):
        raise ValueError('Candidate universe changed during price study')
    results['raw_source_sha256']=candidate_report['raw_source_sha256']
    results['bars_sha256']=candidate_report['bars_sha256']
    results['candidate_counts']=candidate_report['candidate_counts']
    results['observed_bars']=candidate_report['observed_bars']
    results['examined_m5_bars']=candidate_report['examined_m5_bars']
    results['missing_or_gapped_context']=candidate_report['missing_or_gapped_context']
    results['source_is_publisher_ohlc_not_broker_bid_ask']=True
    results['strategy_was_designed_after_seeing_in_sample_period']=True
    results['not_out_of_sample']=True
    return results


def main():
    p=argparse.ArgumentParser()
    p.add_argument('raw_source');p.add_argument('bars_dir');p.add_argument('output')
    a=p.parse_args()
    out=Path(a.output)
    if out.exists() or out.is_symlink():
        p.error('Refuse to overwrite existing research evidence')
    results=report(a.raw_source,a.bars_dir)
    with out.open('x',encoding='utf-8') as f:
        json.dump(results,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps(dict(cohorts=results['cohorts'],
        actual_win_rate_pct=results['actual_win_rate_pct'],
        net_expectancy_r=results['net_expectancy_r']),allow_nan=False))


if __name__=='__main__':
    main()
