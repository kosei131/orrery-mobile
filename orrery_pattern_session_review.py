# SPDX-License-Identifier: GPL-3.0-only
"""Bounded summer weekly-clock sensitivity, NOT authenticated historical sessions."""
from bisect import bisect_left
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from orrery_paired_archive_study import SOURCE_PINS, read_side, evaluate_plan, summary, iso, at
from orrery_pattern_robustness import load_parent, MANIFEST_SHA256, one_position

START=at('2026-09-01T00:00:00+00:00')
END=at('2026-10-20T00:00:00+00:00')
SPECIAL={'2026-09-07'}
SPEC={
    'scope':'2026-09-01 inclusive to 2026-10-20 exclusive UTC; summer only',
    'weekly_clock':'Sunday 22:00 to Friday 21:00 UTC; daily break 21:00 to 22:00 UTC',
    'special_dates_unresolved':sorted(SPECIAL),
    'candidate_and_signal_changes':False,
    'missing_price_interpolation':False,
    'closure_scenario':'Skip only routine-clock-closed missing minutes, then use actual paired reopening quote.',
    'timeout':'120 wall-clock minutes; if closed, defer exit to observed reopening open.',
    'reopen_priority':'Adverse stop at observed open; favorable target capped at target; then overdue timeout.',
    'unknown_gap':'Preserve censoring; no assumed exit or subsequent-position release.',
    'calendar_authenticated':False,
    'source_authenticity_verified':False,
    'net_costs_known':False,
}
SOURCES=[
    dict(url='https://www.dukascopy.com/wiki/en/manuals/jforex4-desktop/trading-sessions/',
         claim='XAU/USD daily trading session 18:00 to 17:00 America/New_York; undated current documentation.'),
    dict(url='https://www.dukascopy.com/swiss/english/about/ournews/-dbl194921/',
         published_utc='2011-04-08',claim='Gold Sunday 22:00 to Friday 21:00 GMT in summer; daily break 21:00 to 22:00.'),
    dict(url='https://www.dukascopy.com/swiss/english/about/ournews/market-closures-on-labor-day-in-the-united-states-dbl203555',
         published_utc='2026-09-04T12:00:00Z',claim='Special bullion breaks on September 7; exact historical table not retrieved.'),
]


def minute_class(t):
    if type(t) is not int or t%60:raise ValueError('UTC minute required')
    if not START<=t<END:return 'OUTSIDE_VERIFIED_RESEARCH_SCOPE'
    d=datetime.fromtimestamp(t,timezone.utc)
    if d.date().isoformat() in SPECIAL:return 'SPECIAL_DATE_UNRESOLVED'
    m=d.hour*60+d.minute;day=d.weekday()
    closed=day==5 or (day==6 and m<1320) or (day==4 and m>=1260) or (day<4 and 1260<=m<1320)
    return 'ROUTINE_CLOSED_CANDIDATE' if closed else 'EXPECTED_OPEN'


def partition(a,z):
    if a>=z or a%60 or z%60 or z-a>8*86400:raise ValueError('Bounded missing interval required')
    return dict(Counter(minute_class(t) for t in range(a,z,60)))


def audit_gaps(bid,ask):
    if not bid or set(bid)!=set(ask):raise ValueError('Exact paired coverage required')
    stamps=sorted(bid);gaps=[];counts=Counter()
    for a,z in zip(stamps,stamps[1:]):
        if z-a<=60:continue
        parts=partition(a+60,z);counts.update(parts)
        gaps.append(dict(first_missing_utc=iso(a+60),reopen_utc=iso(z),missing_minutes=(z-a)//60-1,
                         partition=parts,routine_only=set(parts)=={'ROUTINE_CLOSED_CANDIDATE'}))
    return dict(paired_minutes=len(stamps),first_open_utc=iso(stamps[0]),last_open_utc=iso(stamps[-1]),
                gap_count=len(gaps),unobserved_minutes=sum(counts.values()),minute_partition=dict(counts),gaps=gaps,
                observed_minutes_in_routine_closed_clock=sum(minute_class(t)=='ROUTINE_CLOSED_CANDIDATE' for t in stamps),
                calendar_authenticated=False,source_authenticity_verified=False,edges_inferred=False)


def closure_scenario(plan,bid,ask,*,structural_stop=None,structural_known_at=None,horizon=120,paired_times=None):
    """Retain strict evaluator unless its first post-entry gap is encountered."""
    strict=evaluate_plan(plan,bid,ask,structural_stop=structural_stop,
                         structural_known_at=structural_known_at,horizon=horizon)
    if strict['status']!='CENSORED_AT_SIDE_GAP':return strict
    t=plan['first_poi_touch_close'];side=plan['side'];buy=side=='BUY'
    entry=ask[t]['open'] if buy else bid[t]['open']
    stop=structural_stop if structural_stop is not None else entry+(-6 if buy else 6)
    risk=entry-stop if buy else stop-entry;target=entry+(1.5*risk if buy else -1.5*risk)
    exit_side=bid if buy else ask;deadline=t+horizon*60;skips=[]
    times=paired_times if paired_times is not None else sorted(set(bid)&set(ask))
    def result(status,**kw):
        return dict(entry_at=t,side=side,status=status,**kw,closure_sensitivity=True,skipped_routine_gaps=skips.copy())
    def resolved(stamp,price,reason,**kw):
        return result('RESOLVED_REFERENCE',r=(price-entry)/risk if buy else (entry-price)/risk,
                      exit_at=stamp,exit_reason=reason,entry=entry,stop=stop,target=target,initial_risk_price=risk,**kw)
    stamp=strict['last_observed_until']
    while True:
        reopened=False
        if stamp not in bid or stamp not in ask:
            i=bisect_left(times,stamp)
            if i==len(times):return result('CENSORED_AT_SIDE_GAP',last_observed_until=stamp,gap_class='SOURCE_END')
            nxt=times[i]
            if nxt-stamp>8*86400:return result('CENSORED_AT_SIDE_GAP',last_observed_until=stamp,gap_class='GAP_BUDGET')
            parts=partition(stamp,nxt)
            if set(parts)!={'ROUTINE_CLOSED_CANDIDATE'}:
                return result('CENSORED_AT_SIDE_GAP',last_observed_until=stamp,gap_class='UNRESOLVED',gap_partition=parts)
            skips.append(dict(first_missing=stamp,reopen_at=nxt,minutes=(nxt-stamp)//60))
            stamp=nxt;reopened=True
        b=exit_side[stamp]
        if b['open']<=stop if buy else b['open']>=stop:
            return resolved(stamp,b['open'],'STOP_AT_OBSERVED_OPEN')
        if reopened and (b['open']>=target if buy else b['open']<=target):
            # Cap favorable gap fills; keep minute-end availability conservative.
            return resolved(stamp,target,'TP_TOUCH',reopen_open_target=True)
        if stamp>=deadline:
            return resolved(stamp,b['open'],'TIMEOUT_CLOSE',timeout_deferred_to_reopen=True,
                            original_deadline=deadline,exit_price_basis='OBSERVED_REOPEN_OPEN')
        sl=b['low']<=stop if buy else b['high']>=stop
        tp=b['high']>=target if buy else b['low']<=target
        if sl and tp:return result('AMBIGUOUS_SAME_MINUTE',exit_at=stamp,r=None,stop_first_reference_r=-1)
        if sl:return resolved(stamp,stop,'SL_TOUCH')
        if tp:return resolved(stamp,target,'TP_TOUCH')
        if stamp+60==deadline:return resolved(deadline,b['close'],'TIMEOUT_CLOSE')
        stamp+=60


def compact_single(rows):
    r=one_position(rows)
    return {k:v for k,v in r.items() if k!='decisions'}


def run(folder,output):
    parent=load_parent();bid={};ask={};files=[]
    for name,pin in SOURCE_PINS.items():
        data,receipt=read_side(Path(folder)/name)
        if receipt['sha256']!=pin:raise ValueError('Pinned input changed')
        dest=bid if name.startswith('bid_') else ask
        if set(dest)&set(data):raise ValueError('Duplicate source clock')
        dest.update(data);files.append(dict(name=name,**receipt))
    audit=audit_gaps(bid,ask);times=sorted(bid)
    if any(ask[t][k]<bid[t][k] for t in times for k in ('open','high','low','close')):raise ValueError('Crossed quote')
    candidates={c['id']:c for c in parent['candidates']};results={};matches=0
    for window,w in parent['results'].items():
        for model,baseline in w['models'].items():
            strict_rows=[];new_rows=[];changes=[]
            for prior in baseline['outcomes']:
                c=candidates[prior['candidate_id']];stop=known=None
                if model.endswith('ANCHOR_EXTREME'):
                    anchor=range(c['anchor_open'],c['anchor_known_at'],60)
                    if any(t not in bid or t not in ask for t in anchor):
                        strict_rows.append(prior);new_rows.append(prior);continue
                    stop=c['anchor_bid_low'] if c['side']=='BUY' else max(ask[t]['high'] for t in anchor)
                    known=c['anchor_known_at']
                plan=dict(first_poi_touch_close=c['entry_at'],side=c['side'])
                opts=dict(structural_stop=stop,structural_known_at=known)
                strict=dict(evaluate_plan(plan,bid,ask,**opts),candidate_id=c['id'])
                if strict!=prior:raise ValueError('Original individual outcome changed')
                r=dict(closure_scenario(plan,bid,ask,paired_times=times,**opts),candidate_id=c['id'])
                strict_rows.append(strict);new_rows.append(r)
                if r!=strict:changes.append(dict(strict=strict,conditional=r))
            if strict_rows!=baseline['outcomes']:raise ValueError('Baseline mismatch')
            matches+=1
            results.setdefault(window,{})[model]=dict(strict=summary(strict_rows),conditional=summary(new_rows),
                strict_single=compact_single(strict_rows),conditional_single=compact_single(new_rows),
                changed_outcomes=changes,
                changed_status_counts=dict(Counter(x['conditional']['status'] for x in changes)),
                max_reference_holding_minutes=max(((r['exit_at']-r['entry_at'])//60 for r in new_rows if r['status']=='RESOLVED_REFERENCE'),default=None),
                deferred_timeout_count=sum(bool(r.get('timeout_deferred_to_reopen')) for r in new_rows),
                all_non_gap_individual_outcomes_unchanged=all(a==b for a,b in zip(strict_rows,new_rows) if a['status']!='CENSORED_AT_SIDE_GAP'))
    report=dict(status='UNAUTHENTICATED_WEEKLY_CLOSURE_SENSITIVITY',specification=SPEC,sources=SOURCES,
        source_files=files,parent_manifest_sha256=MANIFEST_SHA256,audit=audit,results=results,
        specification_sha256=sha256(json.dumps(SPEC,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        baseline_twelve_models_exact_match=matches==12,code_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        adopted=False,execution_allowed=False,independent_holdout=False,formal_lsr02=False,
        calendar_authenticated=False,net_expectancy_r=None,account_return_pct=None,account_max_dd_usd=None,
        limitations=['Weekly clock consistency is not authentication of the third-party source or historical holiday calendar.',
                    'September 7 special session and September 30 22:28 UTC absence remain unresolved.',
                    'Same frozen inspected candidates, no rebuilding indicators across gaps or interpolation.',
                    'Reopening/overdue exits are explicit conditional quote-reference assumptions, not actual fills.',
                    'Unknown fees, extra slippage, swap, margin and account risk controls; overlapping candidates kept.',
                    'One-position windows start flat independently; positions may exit after their entry-window end.'])
    with Path(output).open('x',encoding='utf-8') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
    return report


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();r=run(a.folder,a.output)
    print(json.dumps(dict(audit={k:v for k,v in r['audit'].items() if k!='gaps'},
                         results={w:{m:dict(strict=x['strict'],conditional=x['conditional'],single=x['conditional_single']['accepted_position_summary'])
                                     for m,x in ms.items() if m=='PULLBACK_RESUME_FIXED_6'} for w,ms in r['results'].items()})))
