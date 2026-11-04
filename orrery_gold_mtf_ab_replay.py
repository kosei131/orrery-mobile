# SPDX-License-Identifier: GPL-3.0-only
"""Pinned public XAUUSD H4/M15/M5 causal A/B candidate replay.

Research hypothesis only. Publisher OHLC is NOT broker Bid/Ask.
Signal counts only: no fabricated entries, fills, wins, R, or account return.
All 3 timeframes are complete-grid bars; holes are never interpolated.
"""
import argparse
from bisect import bisect_right
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from orrery_real_bars_lsr_bridge import load
from orrery_gold_mtf_ab_hypotheses import candidate

RAW_PIN='a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225'
MAX_M5_BARS=150000
TF=('H4','M15','M5')
STEPS={'H4':14400,'M15':900,'M5':300}
WINDOWS={'H4':3,'M15':13,'M5':18}


def _recent(bars,closes,at,tf):
    n=bisect_right(closes,at)
    window=bars[max(0,n-WINDOWS[tf]):n]
    if not window or at-window[-1]['close_time']>=STEPS[tf]:
        return []
    if len(window)<WINDOWS[tf]:
        return []
    if any(b['close_time']-a['close_time']!=STEPS[tf]
           for a,b in zip(window,window[1:])):
        return []
    return window


def run(source,bars_dir,*,expected_source_sha256=RAW_PIN):
    source=Path(source);bars_dir=Path(bars_dir)
    if sha256(source.read_bytes()).hexdigest()!=expected_source_sha256:
        raise ValueError('Pinned raw source has changed')
    frames={}
    hashes={}
    for tf in TF:
        path=bars_dir/f'XAUUSD_{tf}_UNVERIFIED_QUOTE.csv'
        result=load(path,tf)
        frames[tf]=result['bars']
        hashes[tf]=sha256(path.read_bytes()).hexdigest()
    if len(frames['M5'])>MAX_M5_BARS:
        raise ValueError('M5 research budget exceeded')
    times={tf:[b['close_time'] for b in frames[tf]] for tf in TF}
    found=[]
    eligibility=Counter()
    for m5_idx,bar in enumerate(frames['M5']):
        at=bar['close_time']
        windows={tf:_recent(frames[tf],times[tf],at,tf) for tf in TF}
        if any(not windows[tf] for tf in TF):
            eligibility['MISSING_CONTIGUOUS_CONTEXT']+=1
            continue
        h4,m15,m5=(windows[tf] for tf in TF)
        try:
            signal=candidate(h4,m15,m5,as_of=at)
        except ValueError as e:
            raise ValueError(f'Invalid pinned sample at M5 index {m5_idx}') from e
        eligibility['CHECKED']+=1
        if signal is not None:
            found.append(signal)
            eligibility[signal['family']]+=1
    if len({x['candidate_id'] for x in found})!=len(found):
        raise ValueError('Duplicate signal IDs')
    return dict(status='PUBLIC_XAU_MTF_AB_CANDIDATE_COUNTS_ONLY',
        raw_source_sha256=expected_source_sha256,bars_sha256=hashes,
        observed_bars={tf:len(frames[tf]) for tf in TF},
        examined_m5_bars=eligibility['CHECKED'],
        missing_or_gapped_context=eligibility['MISSING_CONTIGUOUS_CONTEXT'],
        candidate_counts={f:eligibility[f] for f in ('A_CONTINUATION','B_COUNTER_SWEEP')},
        candidates=found,quote_basis_verified=False,entry_fills_verified=False,
        out_of_sample=False,actual_win_rate_pct=None,net_expectancy_r=None,
        actual_profit_usd=None,account_return_pct=None,
        execution_allowed=False,adoption_allowed=False)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('raw_source');p.add_argument('bars_dir');p.add_argument('output')
    args=p.parse_args()
    out=Path(args.output)
    if out.exists() or out.is_symlink():
        p.error('Refuse to overwrite evidence')
    report=run(args.raw_source,args.bars_dir)
    with out.open('x',encoding='utf-8') as fh:
        json.dump(report,fh,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps(dict(candidate_counts=report['candidate_counts'],
                          examined_m5_bars=report['examined_m5_bars'],
                          missing_or_gapped_context=report['missing_or_gapped_context'])))


if __name__=='__main__':
    main()
