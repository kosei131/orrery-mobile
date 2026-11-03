# SPDX-License-Identifier: GPL-3.0-only
"""Causal confirmed-M15 level room; descriptive cohorts, no signal changes."""
from bisect import bisect_right
from hashlib import sha256
from math import isfinite
from pathlib import Path
from tempfile import TemporaryDirectory
import csv,json
from lsr02_structure import detect
from orrery_m1_complete_bars import aggregate
from orrery_real_bars_lsr_bridge import load
from orrery_paired_archive_study import SOURCE_PINS,read_side,iso,summary
from orrery_pattern_robustness import load_parent,MANIFEST_SHA256


def room(bars, *, at,side,entry,risk):
    if type(at) is not int or side not in ('BUY','SELL') or any(type(v) not in (int,float) or not isfinite(v) or v<=0 for v in (entry,risk)):
        raise ValueError('Known clock, side and positive geometry required')
    times=[b['close_time'] for b in bars]
    if any(b<=a for a,b in zip(times,times[1:])):raise ValueError('Ordered M15 clocks required')
    i=bisect_right(times,at)
    out=dict(group='UNKNOWN',reason='NO_CURRENT_M15',level=None,level_known_at=None,room_r=None,context_bars=0)
    if not i or at-times[i-1]>=900:return out
    begin=i-1
    while begin>0 and i-begin<300 and times[begin]-times[begin-1]==900:begin-=1
    known=bars[begin:i];out['context_bars']=len(known)
    pivots=detect(known,as_of=at,interval=900,left=2,right=2)['pivots']
    kind='HIGH' if side=='BUY' else 'LOW';sign=1 if side=='BUY' else -1
    eligible=[p for p in pivots if p['kind']==kind and sign*(p['price']-entry)>0]
    if not eligible:out['reason']='NO_CONFIRMED_OPPOSING_LEVEL';return out
    p=min(eligible,key=lambda p:(abs(p['price']-entry),-p['known_at']))
    rr=sign*(p['price']-entry)/risk
    return dict(group='ROOM_GE_1_5R' if rr>=1.5 else 'ROOM_LT_1_5R',reason='CONFIRMED_PIVOT_LEVEL',
                level=p['price'],level_known_at=p['known_at'],room_r=rr,context_bars=len(known))


def geometry(c,policy,bid,ask):
    t=c['entry_at'];side=c['side']
    if t not in bid or t not in ask:return None
    entry=ask[t]['open'] if side=='BUY' else bid[t]['open']
    if policy=='FIXED_6':return entry,6.
    if policy!='ANCHOR_EXTREME':raise ValueError('Fixed explicit SL policy required')
    stamps=range(c['anchor_open'],c['anchor_known_at'],60)
    if not stamps or any(t not in bid or t not in ask for t in stamps):return None
    stop=c['anchor_bid_low'] if side=='BUY' else max(ask[t]['high'] for t in stamps)
    risk=entry-stop if side=='BUY' else stop-entry
    return (entry,risk) if risk>0 else None


def run(folder,output,annotations):
    parent=load_parent();bid={};ask={};folder=Path(folder)
    for name,pin in SOURCE_PINS.items():
        rows,a=read_side(folder/name)
        if a['sha256']!=pin:raise ValueError('Pinned source changed')
        dest=bid if name.startswith('bid_') else ask
        if set(dest)&set(rows):raise ValueError('Duplicate input clocks')
        dest.update(rows)
    if set(bid)!=set(ask):raise ValueError('Exact paired clocks required')
    if any(ask[t][k]<bid[t][k] for t in bid for k in ('open','high','low','close')):raise ValueError('Crossed side OHLC')
    frames={}
    with TemporaryDirectory() as tmp:
        for side,values in (('BUY',bid),('SELL',ask)):
            src=Path(tmp)/(side+'.csv');dst=Path(tmp)/(side+'_M15.csv')
            with src.open('w',newline='') as f:
                w=csv.writer(f);w.writerow(['timestamp_utc','bid_open','bid_high','bid_low','bid_close'])
                for t,b in sorted(values.items()):w.writerow([iso(t),b['open'],b['high'],b['low'],b['close']])
            aggregate(src,dst,'M15');frames[side]=load(dst,'M15')['bars']
    candidates={c['id']:c for c in parent['candidates']};models={};rows=[]
    for window,w in parent['results'].items():
        models[window]={}
        for model,base in w['models'].items():
            policy='ANCHOR_EXTREME' if model.endswith('ANCHOR_EXTREME') else 'FIXED_6'
            groups={g:[] for g in ('ROOM_GE_1_5R','ROOM_LT_1_5R','UNKNOWN')}
            for outcome in base['outcomes']:
                c=candidates[outcome['candidate_id']];shape=geometry(c,policy,bid,ask)
                a=(room(frames[c['side']],at=c['entry_at'],side=c['side'],entry=shape[0],risk=shape[1]) if shape else
                   dict(group='UNKNOWN',reason='UNKNOWN_OR_INVALID_ENTRY_GEOMETRY',level=None,level_known_at=None,room_r=None,context_bars=0))
                groups[a['group']].append(outcome)
                rows.append(dict(window=window,model=model,candidate_id=c['id'],entry_at=c['entry_at'],side=c['side'],**a))
            baseline=summary(base['outcomes'])
            if any(base[k]!=v for k,v in baseline.items()):raise ValueError('Parent baseline mismatch')
            if sum(len(v) for v in groups.values())!=len(base['outcomes']):raise ValueError('Population mismatch')
            models[window][model]=dict(baseline=baseline,groups={g:summary(v) for g,v in groups.items()})
    with Path(annotations).open('x',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    r=dict(status='CONFIRMED_M15_LEVEL_ROOM_COHORTS_ONLY',models=models,
        definition=dict(left=2,right=2,max_contiguous_bars=300,minimum_room_r=1.5,
                        buy_levels='BID_M15_HIGH',sell_levels='ASK_M15_LOW'),
        parent_manifest_sha256=MANIFEST_SHA256,source_pins=SOURCE_PINS,
        annotations_sha256=sha256(Path(annotations).read_bytes()).hexdigest(),
        code_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        parameter_sets_tried=1,baseline_outcomes_unchanged=True,out_of_sample=False,
        formal_lsr02=False,halftrend_compared=True,reversal04_compared=False,
        execution_allowed=False,adopted=False,net_expectancy_r=None,account_return_pct=None,account_max_dd_usd=None,
        limitations=['Known M15 pivots are a level hypothesis, not certified support/resistance.',
            'All 12 existing models and every group retained; no ex-post winner selection.',
            'Same inspected periods; no independent unused period.',
            'Existing bid/ask price outcomes only; fees/slippage/swap and account gates unverified.',
            'No level or entry geometry is UNKNOWN, not evidence of unlimited room.',
            'H4 formal LSR01/02, Reversal04, undefined 2.6 and external indicator parity not integrated.'])
    with Path(output).open('x',encoding='utf-8') as f:json.dump(r,f,indent=2,allow_nan=False);f.write('\n')
    return r

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('output',type=Path);p.add_argument('annotations',type=Path);a=p.parse_args()
    run(a.folder,a.output,a.annotations)
