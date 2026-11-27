# SPDX-License-Identifier: GPL-3.0-only
"""Third-party bid/ask OHLC research. Not authenticated feed or account returns."""
from collections import Counter
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from orrery_m1_complete_bars import aggregate
from orrery_real_bars_lsr_bridge import load
from orrery_entry_universe_study import confirmations
from orrery_public_xau_sequence_study import observe_retest
from orrery_xau_confirmation_entry_comparison import entry_plans

REVISION='b60bd71d0e34a42cb962daf688ff252e73f409ca'
BASE='https://raw.githubusercontent.com/kevingtlin/Market-Data-Lab/'+REVISION

SOURCE_PINS={
 'bid_2026_09.csv':'09cc828da25ee817719c3fb5b3be22058f62d6f7b991ca00f7102a381953e325',
 'ask_2026_09.csv':'697c9079a8ed80eb2716604f27900e4352206db0a62847510530efdcfaf3645d',
 'bid_2026_10.csv':'05cdf7ebea1932a6a4748ed47ad74fe2de0023bb11f9b835c38bba424358dd7d',
 'ask_2026_10.csv':'43d37686754e87fd343d14012832fd476b47551d390a15520fb62963f2ff74c0',
}



def read_side(path):
    path=Path(path)
    if path.stat().st_size>20*1024*1024:raise ValueError('CSV budget exceeded')
    rows={};prev=None;longest=flat=0;lastprice=None;gaps=[]
    with path.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=['timestamp','open','high','low','close']:raise ValueError('Exact side schema required')
        for r in reader:
            stamp=r['timestamp']
            if not stamp.isdecimal() or len(stamp)>16 or int(stamp)%60000:raise ValueError('UTC millisecond minute required')
            t=int(stamp)//1000
            if prev is not None and t<=prev:raise ValueError('Duplicate or unordered side clock')
            if t+60>datetime.now(timezone.utc).timestamp():raise ValueError('Unclosed archive minute')
            b={k:float(r[k]) for k in ('open','high','low','close')}
            if not all(isfinite(v) for v in b.values()) or not 0<b['low']<=min(b['open'],b['close'])<=max(b['open'],b['close'])<=b['high']:
                raise ValueError('Invalid side OHLC')
            if prev is not None and t-prev>60:gaps.append(dict(after=prev,before=t,unobserved_minutes=(t-prev)//60-1))
            isflat=b['open']==b['high']==b['low']==b['close']
            flat=(flat+1 if prev is not None and t-prev==60 and isflat and lastprice==b['close'] else 1 if isflat else 0)
            longest=max(longest,flat);lastprice=b['close'];prev=t;rows[t]=b
            if len(rows)>60000:raise ValueError('Monthly row budget exceeded')
    if not rows:raise ValueError('Empty side archive')
    return rows,dict(sha256=sha256(path.read_bytes()).hexdigest(),rows=len(rows),
        first_open_utc=iso(min(rows)),last_open_utc=iso(max(rows)),
        gaps=len(gaps),unobserved_minutes=sum(g['unobserved_minutes'] for g in gaps),
        gap_examples=gaps[:10],longest_identical_flat_minutes=longest)


def iso(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()
def at(s):return int(datetime.fromisoformat(s).timestamp())


def evaluate_plan(plan, bid, ask, *, structural_stop=None, structural_known_at=None, horizon=120):
    t=plan['first_poi_touch_close'];side=plan['side']
    if side not in ('BUY','SELL') or type(horizon) is not int or horizon<1:raise ValueError('Invalid execution specification')
    def output(status,**kw):return dict(entry_at=t,side=side,status=status,**kw)
    if t not in bid or t not in ask:return output('UNKNOWN_ENTRY_HISTORY')
    entry=ask[t]['open'] if side=='BUY' else bid[t]['open']
    stop=structural_stop if structural_stop is not None else entry+(-6 if side=='BUY' else 6)
    if not isfinite(stop) or stop<=0:raise ValueError('Invalid structural stop')
    if structural_stop is not None:
        known=structural_known_at
        if type(known) is not int or known>t or (t-known)%60:raise ValueError('Causal structural clock required')
        for stamp in range(known,t,60):
            if stamp not in bid or stamp not in ask:return output('UNKNOWN_PRE_ENTRY_HISTORY')
            if (bid[stamp]['low']<=stop if side=='BUY' else ask[stamp]['high']>=stop):
                return output('STRUCTURE_BREACHED_BEFORE_ENTRY')
    distance=entry-stop if side=='BUY' else stop-entry
    exit_side=bid if side=='BUY' else ask
    if distance<=0 or (exit_side[t]['open']<=stop if side=='BUY' else exit_side[t]['open']>=stop):
        return output('STOP_INVALID_AT_ENTRY')
    target=entry+(1.5*distance if side=='BUY' else -1.5*distance)
    def resolved(stamp,price,reason):
        value=(price-entry)/distance if side=='BUY' else (entry-price)/distance
        return output('RESOLVED_REFERENCE',r=value,exit_at=stamp,exit_reason=reason,
                      entry=entry,stop=stop,target=target,initial_risk_price=distance)
    for stamp in range(t,t+horizon*60,60):
        if stamp not in bid or stamp not in ask:return output('CENSORED_AT_SIDE_GAP',last_observed_until=stamp)
        b=exit_side[stamp]
        if b['open']<=stop if side=='BUY' else b['open']>=stop:
            return resolved(stamp,b['open'],'STOP_AT_OBSERVED_OPEN')
        sl=b['low']<=stop if side=='BUY' else b['high']>=stop
        tp=b['high']>=target if side=='BUY' else b['low']<=target
        if sl and tp:return output('AMBIGUOUS_SAME_MINUTE',exit_at=stamp,r=None,stop_first_reference_r=-1)
        if sl:return resolved(stamp,stop,'SL_TOUCH')
        if tp:return resolved(stamp,target,'TP_TOUCH')
    return resolved(t+horizon*60,exit_side[t+(horizon-1)*60]['close'],'TIMEOUT_CLOSE')


def summary(rows):
    rs=[r['r'] for r in rows if r['status']=='RESOLVED_REFERENCE']
    gains=sum(r for r in rs if r>0);loss=-sum(r for r in rs if r<0)
    return dict(entry_plans=len(rows),status_counts=dict(Counter(r['status'] for r in rows)),
        resolved=len(rs),positive=sum(r>0 for r in rs),
        positive_rate_pct=round(100*sum(r>0 for r in rs)/len(rs),4) if rs else None,
        total_resolved_reference_r=round(sum(rs),5) if rs else None,
        mean_resolved_reference_r=round(sum(rs)/len(rs),5) if rs else None,
        pf_resolved_reference=round(gains/loss,5) if loss else None,
        net_expectancy_r=None,account_return_pct=None,account_max_dd_usd=None)


def run(root,output):
    root=Path(root);bid={};ask={};files=[]
    for month in ('2026_09','2026_10'):
        for side,all_rows in (('bid',bid),('ask',ask)):
            p=root/(side+'_'+month+'.csv');rows,audit=read_side(p)
            if audit['sha256']!=SOURCE_PINS[p.name]:raise ValueError('Pinned source bytes changed')
            if any(datetime.fromtimestamp(t,timezone.utc).strftime('%Y_%m')!=month for t in rows):
                raise ValueError('Source month mismatch')
            if set(rows)&set(all_rows):raise ValueError('Overlapping source files')
            if audit['longest_identical_flat_minutes']>=60:raise ValueError('Long flat archive rows require source review')
            all_rows.update(rows)
            files.append(dict(side=side,month=month,source_url=BASE+'/xauusd/'+side+'/m1/xauusd_'+side+'_m1_'+month+'.csv',**audit))
    shared=sorted(set(bid)&set(ask));crossings=[]
    for t in shared:
        if any(ask[t][k]<bid[t][k] for k in ('open','close','high','low')):crossings.append(t)
    if crossings:raise ValueError('Crossed side OHLC requires source review')
    dest=root/'bid_bars';dest.mkdir(exist_ok=True)
    normalized=dest/'M1.csv'
    with normalized.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['timestamp_utc','bid_open','bid_high','bid_low','bid_close'])
        for t,b in sorted(bid.items()):w.writerow([iso(t),b['open'],b['high'],b['low'],b['close']])
    aggregations={label:aggregate(normalized,dest/(label+'.csv'),label) for label in ('M5','M15')}
    m15=load(dest/'M15.csv','M15')['bars'];m5=load(dest/'M5.csv','M5')['bars']
    universe=confirmations(m15,m5);by_sweep={b['close_time']:b for b in m15}
    windows={'PREVIOUS_CALENDAR_OVERLAP':('2026-09-01T00:00:00+00:00','2026-09-25T00:00:00+00:00'),
             'AFTER_GETDATA_WINDOW':('2026-09-26T00:00:00+00:00','2026-10-19T14:00:00+00:00')}
    results={}
    for name,(start,end) in windows.items():
        a,z=at(start),at(end);candidates=[c for c in universe if a<=c['confirmation_close']<z]
        observations={(c['sweep_close'],c['confirmation_close'],c['side']):observe_retest(c,m5) for c in candidates}
        models={}
        for scope,cs in (('ALL',candidates),('VHF_PASS',[c for c in candidates if c['vhf_pass']])):
            for mode in ('CONFIRMATION','RETEST'):
                plans,skips=entry_plans(cs,mode=mode,observations=observations,start=a,end=z)
                for policy in ('FIXED_6','SWEEP_EXTREME'):
                    outcomes=[]
                    for p in plans:
                        stop=known=None
                        if policy=='SWEEP_EXTREME':
                            sweep=p['sweep_close'];sweep_open=by_sweep[sweep]['open_time']
                            if any(t not in bid or t not in ask for t in range(sweep_open,sweep,60)):
                                outcomes.append(dict(entry_at=p['first_poi_touch_close'],side=p['side'],status='UNKNOWN_SWEEP_SIDE_HISTORY'));continue
                            stop=by_sweep[sweep]['low'] if p['side']=='BUY' else max(ask[t]['high'] for t in range(sweep_open,sweep,60))
                            known=sweep
                        outcomes.append(evaluate_plan(p,bid,ask,structural_stop=stop,structural_known_at=known))
                    models[scope+'_'+mode+'_'+policy]=dict(confirmation_universe=len(cs),
                        no_entry_reasons=dict(Counter(s['reason'] for s in skips)),**summary(outcomes),outcomes=outcomes)
        results[name]=dict(start_utc=start,end_utc=end,models=models)
    spreads=[ask[t]['close']-bid[t]['close'] for t in shared]
    ordered=sorted(spreads)
    report=dict(status='THIRD_PARTY_PAIRED_OHLC_EXPLORATORY_STUDY',source_revision=REVISION,
        files=files,bid_rows=len(bid),ask_rows=len(ask),shared_rows=len(shared),
        bid_only=len(set(bid)-set(ask)),ask_only=len(set(ask)-set(bid)),crossed_side_rows=0,
        close_side_difference_price_units=dict(min=min(spreads),median=ordered[len(ordered)//2],max=max(spreads)),
        aggregations=aggregations,full_source_confirmations=len(universe),results=results,
        code_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        net_expectancy_r=None,account_return_pct=None,account_max_dd_usd=None,
        execution_allowed=False,adopted=False,independent_holdout_verified=False,
        source_authenticity_verified=False,session_completeness_verified=False,formal_lsr02=False,
        assumptions=dict(target_r=1.5,holding_minutes=120,retest_minutes=60,signal_side='BID',h4_filter=False),
        limitations=['Third-party archive, not authenticated direct broker feed or MT5 account fills.',
                    'Close bid/ask difference is not synchronized tick spread.',
                    'OHLC barrier time/order unknown; dual touches remain ambiguous.',
                    'Fees, extra slippage, swaps, margin and account risk stops not evaluated.',
                    'Later period overlaps prior TradingView research; not certified out-of-sample.',
                    'Older calendar-flat files rejected, no flat-row filtering or interpolation performed.'])
    with Path(output).open('x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:{name:{x:y for x,y in v.items() if x!='outcomes'} for name,v in w['models'].items()} for k,w in results.items()}))
    return report

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.root,a.output)
