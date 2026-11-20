# SPDX-License-Identifier: GPL-3.0-only
"""Causal M5 sequence hypotheses, not formal LSR02 Type A/B or WT_X parity."""
from collections import Counter
import csv
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from tempfile import TemporaryDirectory
from lsr05_halftrend import calculate, SOURCE_SHA256
from lsr03_learning_rollup import _sequence
from orrery_public_xau_sequence_study import segments
from orrery_m1_complete_bars import aggregate
from orrery_real_bars_lsr_bridge import load
from orrery_paired_archive_study import read_side, SOURCE_PINS, REVISION, BASE, iso, at, evaluate_plan, summary

FAMILIES=('FLIP_REFERENCE','PULLBACK_RESUME','REVERSAL_CONFIRM')
CONFIG=dict(amplitude=2,channel_deviation=2,atr_period=100,interval=300,
            wait_bars=6,line_slope_bars=3,touch_atr=.5,max_entry_distance_atr=1,
            target_r=1.5,horizon_minutes=120)


def walk(bars,ht):
    if len(bars)!=len(ht):raise ValueError('Matched bar and indicator rows required')
    candidates=[];counts=Counter();arms={};last=None
    def emit(family,i,anchor):
        b=bars[i];a=bars[anchor['index']];r=ht[i]
        candidates.append(dict(id=f"{family}:{a['close_time']}:{b['close_time']}:{anchor['side']}",
            family=family,side=anchor['side'],entry_at=b['close_time'],
            anchor_known_at=a['close_time'],anchor_open=a['open_time'],
            anchor_bid_low=a['low'],anchor_bid_high=a['high'],trigger=anchor['trigger'],
            signal_close=b['close'],ht_line=r['line'],atr=r['atr'],
            distance_atr=abs(b['close']-r['line'])/r['atr']))
        counts[family+'_CANDIDATES']+=1
    for i,(b,r) in enumerate(zip(bars,ht)):
        t=b['close_time']
        if r['at']!=t or last is not None and t-last!=300:raise ValueError('Contiguous matched closed clocks required')
        last=t
        if not r['ready']:
            counts['NOT_READY_ROWS']+=1;arms.clear();continue
        if r['state'] not in ('UP','DOWN') or not all(type(r[k]) in (int,float) and isfinite(r[k]) for k in ('line','atr')) or r['atr']<=0:
            raise ValueError('Finite ready HalfTrend state required')
        counts['READY_ROWS']+=1
        side='BUY' if r['state']=='UP' else 'SELL'
        for family,arm in list(arms.items()):
            a=bars[arm['index']];up=arm['side']=='BUY';age=i-arm['index'];reason=None
            if arm['side']!=side:reason='DIRECTION_CHANGED'
            elif b['low']<=a['low'] if up else b['high']>=a['high']:reason='ANCHOR_BREACHED'
            elif age>6:reason='EXPIRED'
            else:
                breakout=b['close']>arm['trigger'] if up else b['close']<arm['trigger']
                line_ok=b['close']>r['line'] if up else b['close']<r['line']
                if breakout and line_ok:
                    if abs(b['close']-r['line'])/r['atr']<=1:
                        emit(family,i,arm);reason='CONFIRMED'
                    else:reason='CHASE_REJECTED'
                elif age==6:reason='EXPIRED'
            if reason:
                counts[family+'_'+reason]+=1;del arms[family]
        if r.get('signal') is not None:
            if r['signal']!=side or r.get('signal_known_at')!=t:raise ValueError('Confirmed matching signal required')
            ref=dict(index=i,side=side,trigger=b['high'] if side=='BUY' else b['low'])
            emit('FLIP_REFERENCE',i,ref)
            if i>=3:
                trigger=max(x['high'] for x in bars[i-3:i]) if side=='BUY' else min(x['low'] for x in bars[i-3:i])
                arms['REVERSAL_CONFIRM']=dict(index=i,side=side,trigger=trigger)
                counts['REVERSAL_CONFIRM_ARMED']+=1
        if 'PULLBACK_RESUME' not in arms and i>=3:
            stable=all(x['ready'] and x['state']==r['state'] for x in ht[i-3:i+1])
            slope=r['line']-ht[i-3]['line']
            slope_ok=slope>0 if side=='BUY' else slope<0
            counter=b['close']<b['open'] if side=='BUY' else b['close']>b['open']
            touch=b['low']<=r['line']+.5*r['atr'] and b['high']>=r['line']-.5*r['atr']
            line_ok=b['close']>r['line'] if side=='BUY' else b['close']<r['line']
            if stable and slope_ok and counter and touch and line_ok:
                arms['PULLBACK_RESUME']=dict(index=i,side=side,trigger=b['high'] if side=='BUY' else b['low'])
                counts['PULLBACK_RESUME_ARMED']+=1
    for family in arms:counts[family+'_PENDING_AT_SEGMENT_END']+=1
    return candidates,dict(counts)


def scan(bars):
    candidates=[];counts=Counter();receipts=[]
    for group in segments(bars,300):
        h=calculate(group,as_of=group[-1]['close_time'],interval=300,amplitude=2,channel_deviation=2,enabled=True)
        rows,funnel=walk(group,h['rows']);candidates.extend(rows);counts.update(funnel)
        receipts.append(dict(start=group[0]['close_time'],end=group[-1]['close_time'],bars=len(group),halftrend_input_sha256=h['input_sha256']))
    if len({c['id'] for c in candidates})!=len(candidates):raise ValueError('Duplicate candidate')
    return candidates,dict(counts),receipts


def sequence(rows,closed_only=False):
    items=[]
    for r in rows:
        resolved=r['status']=='RESOLVED_REFERENCE'
        if closed_only and not resolved:continue
        items.append(dict(reference=r['r'] if resolved else None,
                          reference_exit_at=r['exit_at']*1000 if resolved else None))
    return _sequence(items,'reference')


def run(root,output):
    root=Path(root);bid={};ask={};pins={}
    for name,pin in SOURCE_PINS.items():
        p=root/name;rows,audit=read_side(p)
        if audit['sha256']!=pin:raise ValueError('Source pin mismatch')
        dest=bid if name.startswith('bid_') else ask
        if set(rows)&set(dest):raise ValueError('Overlapping input')
        dest.update(rows);pins[name]=pin
    if set(bid)!=set(ask):raise ValueError('Exact paired minute coverage required')
    if any(ask[t][k]<bid[t][k] for t in bid for k in ('open','high','low','close')):raise ValueError('Crossed side OHLC')
    with TemporaryDirectory() as tmp:
        m1=Path(tmp)/'m1.csv';m5=Path(tmp)/'m5.csv'
        with m1.open('w',newline='') as f:
            w=csv.writer(f);w.writerow(['timestamp_utc','bid_open','bid_high','bid_low','bid_close'])
            for t,b in sorted(bid.items()):w.writerow([iso(t),b['open'],b['high'],b['low'],b['close']])
        agg=aggregate(m1,m5,'M5');bars=load(m5,'M5')['bars']
    candidates,funnel,receipts=scan(bars)
    windows={'PREVIOUS_CALENDAR_OVERLAP':('2026-09-01T00:00:00+00:00','2026-09-25T00:00:00+00:00'),
             'AFTER_GETDATA_WINDOW':('2026-09-26T00:00:00+00:00','2026-10-19T14:00:00+00:00')}
    results={}
    for window,(a,z) in windows.items():
        selected=[c for c in candidates if at(a)<=c['entry_at']<at(z)];models={}
        for family in FAMILIES:
            cs=[c for c in selected if c['family']==family]
            for policy in ('FIXED_6','ANCHOR_EXTREME'):
                outcomes=[]
                for c in cs:
                    stop=known=None
                    if policy=='ANCHOR_EXTREME':
                        times=range(c['anchor_open'],c['anchor_known_at'],60)
                        if any(t not in bid or t not in ask for t in times):
                            outcomes.append(dict(entry_at=c['entry_at'],side=c['side'],status='UNKNOWN_ANCHOR_SIDE_HISTORY',candidate_id=c['id']));continue
                        stop=c['anchor_bid_low'] if c['side']=='BUY' else max(ask[t]['high'] for t in times)
                        known=c['anchor_known_at']
                    o=evaluate_plan(dict(first_poi_touch_close=c['entry_at'],side=c['side']),bid,ask,
                                    structural_stop=stop,structural_known_at=known)
                    outcomes.append(dict(o,candidate_id=c['id']))
                resolved=[r for r in outcomes if r['status']=='RESOLVED_REFERENCE']
                overlaps=sum(b['entry_at']<=a['exit_at']+60 and a['entry_at']<=b['exit_at']+60 for i,a in enumerate(resolved) for b in resolved[i+1:])
                models[family+'_'+policy]=dict(**summary(outcomes),outcomes=outcomes,
                    by_side={side:summary([r for r in outcomes if r['side']==side]) for side in ('BUY','SELL')},
                    all_candidate_reference_sequence=sequence(outcomes),resolved_only_reference_sequence=sequence(outcomes,True),
                    potential_minute_clock_overlap_pairs_resolved_only=overlaps)
        results[window]=dict(start_utc=a,end_utc=z,models=models)
    report=dict(status='M5_HALFTREND_SEQUENCE_HYPOTHESES_NOT_FORMAL_LSR02',config=CONFIG,
        source_revision=REVISION,source_base_url=BASE,source_pins=pins,source_bid_rows=len(bid),source_ask_rows=len(ask),
        aggregation=agg,segment_receipts=receipts,funnel=funnel,candidates=candidates,results=results,
        halftrend_source_sha256=SOURCE_SHA256,code_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        execution_allowed=False,adopted=False,formal_lsr02=False,wt_x_reproduced=False,independent_holdout_verified=False,
        tradingview_indicator_parity_verified=False,net_expectancy_r=None,account_return_pct=None,account_max_dd_usd=None,
        limitations=['Prior inspected third-party archive, not authenticated direct feed or independent OOS.',
            'Local M5 continuation/reversal hypotheses; H4 and WT_X are not applied.',
            'No fees, extra slippage, swaps, portfolio stops or margin replay.',
            'Overlaps are retained, not a feasible account portfolio; closed-only R drawdown is not account DD.',
            'Gaps reset HalfTrend and setups. ATR100 warmup excludes early session observations.',
            'Unconfirmed or expired setups are not trade losses; unknown outcomes are not zero R.'])
    with Path(output).open('x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({w:{name:{k:v for k,v in m.items() if k not in ('outcomes','by_side')} for name,m in r['models'].items()} for w,r in results.items()}))
    return report

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.root,a.output)
