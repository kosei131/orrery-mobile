# SPDX-License-Identifier: GPL-3.0-only
"""One causal 15-minute weak-start exit, including pre-landmark outcomes."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from orrery_gold_ab_archive_comparison import aggregate_complete
from orrery_gold_entry_routing import START as Q2_START, END as Q2_END, load as load_q2
from orrery_gold_h1_half_target import candidates, replay_target
from orrery_gold_h1_state import EVIDENCE, COST, describe
from orrery_gold_nested_wave_october import complete_m5
from orrery_gold_pullback_study import START, END, load_archive, evaluate_pullback
from orrery_gold_session_breakout import Q4_START, load_q4
from orrery_gold_session_hourly import HORIZON, open_horizon

CHECK_MINUTES=15
NATIVE_CLOSES={'TIMEOUT_CLOSE','SESSION_CLOSE','PERIOD_END_CLOSE'}


def evaluate_motion(signal,bid,ask,horizon):
    at=signal['at_utc'];side=signal['side'];buy=side=='BUY';sign=1 if buy else -1
    if at not in bid or at not in ask:
        return dict(status='UNKNOWN_ENTRY_HISTORY',checkpoint_state='UNAVAILABLE')
    entry=(ask if buy else bid)[at]['open']
    stop=(bid if buy else ask)[at]['open']-sign*signal['stop_distance']
    target=entry+2*(entry-stop)
    def original(minutes):
        return evaluate_pullback(dict(first_poi_touch_close=at,side=side),bid,ask,
            structural_stop=stop,structural_known_at=at,target_price=target,horizon=minutes)
    prefix=original(min(CHECK_MINUTES,horizon))
    if prefix['status']!='RESOLVED_REFERENCE' or prefix['exit_reason']!='TIMEOUT_CLOSE':
        return dict(prefix,checkpoint_state='EXIT_OR_UNKNOWN_BEFORE_CHECK')
    if horizon<=CHECK_MINUTES:
        return dict(prefix,checkpoint_state='NATIVE_BOUNDARY_BEFORE_CHECK')
    check=at+CHECK_MINUTES*60
    net=prefix['r']-COST/prefix['initial_risk_price']
    checkpoint=dict(checkpoint_at=check,checkpoint_known_at=check,
        checkpoint_net_r=net,checkpoint_state='STRONG_HOLD' if net>0 else 'WEAK_EXIT_REQUESTED')
    if net>0:
        return dict(original(horizon),**checkpoint)
    if check not in bid or check not in ask:
        return dict(status='CENSORED_AT_SIDE_GAP',entry_at=at,side=side,
                    last_observed_until=check,**checkpoint)
    # Decision uses the previous completed minute; execution uses only the
    # next minute's open, with pre-existing protective barriers taking priority.
    price=(bid if buy else ask)[check]['open']
    if sign*(price-stop)<=0:
        reason='STOP_AT_OBSERVED_OPEN'
    elif sign*(price-target)>=0:
        price=target;reason='TP_TOUCH'
    else:
        reason='WEAK_15M_NEXT_OPEN'
    return dict(prefix,r=sign*(price-entry)/prefix['initial_risk_price'],
                exit_at=check,exit_reason=reason,**checkpoint)


def replay_motion(found,bid,ask,end):
    rows=[];available=0;skips=Counter()
    for signal in found:
        at=signal['at_utc']
        if at<available:
            skips['OCCUPIED_OR_UNKNOWN_OUTCOME']+=1;continue
        horizon=open_horizon(at,end)
        if not horizon:
            skips['CLOSED_OR_PERIOD_END']+=1;continue
        result=evaluate_motion(signal,bid,ask,horizon)
        if result['status']=='RESOLVED_REFERENCE':
            if result['exit_reason']=='TIMEOUT_CLOSE' and horizon<HORIZON:
                result['exit_reason']='PERIOD_END_CLOSE' if at+horizon*60==end else 'SESSION_CLOSE'
            available=result['exit_at']+(0 if result['exit_reason'] in NATIVE_CLOSES else 60)
        elif result['status'] in ('CENSORED_AT_SIDE_GAP','AMBIGUOUS_SAME_MINUTE'):
            available=at+horizon*60
        row=dict(signal,**result)
        if at in bid and at in ask:row['horizon_minutes']=horizon
        rows.append(row)
    return rows,dict(skips)


def checkpoint_diagnostic(rows,bid,ask,end):
    """Describe all baseline entries, including those not reaching the landmark."""
    annotated=[]
    for row in rows:
        result=evaluate_motion(row,bid,ask,open_horizon(row['at_utc'],end))
        state=result['checkpoint_state']
        annotated.append(dict(row,checkpoint_state=state,
            checkpoint_at=result.get('checkpoint_at'),checkpoint_known_at=result.get('checkpoint_known_at'),
            checkpoint_net_r=result.get('checkpoint_net_r')))
    states=sorted({r['checkpoint_state'] for r in annotated})
    return dict(baseline_entries=len(rows),states={s:describe([r for r in annotated if r['checkpoint_state']==s]) for s in states},
                post_entry_landmark=True,entry_time_predictor=False)


def measure(bid,ask,m5,start,end,expected):
    found=list(candidates(aggregate_complete(m5,3600),bid,ask,end))
    baseline,base_skip=replay_target(found,bid,ask,end,2)
    half,half_skip=replay_target(found,bid,ask,end,.5)
    if dict(TP_2R=baseline,TP_05R=half)!=expected:
        raise ValueError('Original 2R/0.5R comparator records did not reproduce')
    managed,managed_skip=replay_motion(found,bid,ask,end)
    months=sorted({datetime.fromtimestamp(t,timezone.utc).strftime('%Y-%m') for t in range(start,end,86400)})
    arms={}
    for name,rows,skip in (('TP_2R',baseline,base_skip),('TP_05R',half,half_skip),('MOTION_15M',managed,managed_skip)):
        arms[name]=dict(describe(rows),skipped=skip,
            by_utc_month={m:describe([r for r in rows if datetime.fromtimestamp(r['at_utc'],timezone.utc).strftime('%Y-%m')==m]) for m in months})
    return dict(start_utc=start,end_utc_exclusive=end,comparators_reproduced=True,passing_signals=len(found),
        arms=arms,checkpoint_states=dict(Counter(r['checkpoint_state'] for r in managed)),
        entries_absent_from_2r=sum(r['at_utc'] not in {b['at_utc'] for b in baseline} for r in managed),
        baseline_checkpoint_diagnostic=checkpoint_diagnostic(baseline,bid,ask,end),
        records=dict(TP_2R=baseline,TP_05R=half,MOTION_15M=managed))


def run(current,prior,q2root):
    raw=(EVIDENCE/'gold_h1_initial_motion_plan.json').read_bytes();plan=json.loads(raw)
    for name,expected in plan['files_sha256'].items():
        if sha256(Path(__file__).parent.joinpath(name).read_bytes()).hexdigest()!=expected:
            raise ValueError('Initial motion plan mismatch: '+name)
    original=json.loads((EVIDENCE/'gold_h1_half_target_results.json').read_text())['periods']
    bid,ask,m5,_,_,_=load_archive(current)
    recent=measure(bid,ask,m5,START,END,original['historical_2026']['records'])
    bid,ask,_,_=load_q4(prior)
    m5=complete_m5({t:bid[t] for t in bid.keys() & ask.keys()},Q4_START,START)
    older=measure(bid,ask,m5,Q4_START,START,original['separate_2025_q4']['records'])
    bid,ask,m5,_=load_q2(q2root)
    q2result=measure(bid,ask,m5,Q2_START,Q2_END,original['separate_2025_q2']['records'])
    return dict(study='gold_h1_initial_motion_v1',plan_sha256=sha256(raw).hexdigest(),
        check_minutes=CHECK_MINUTES,gate_cost_price=COST,hypotheses_replayed=1,
        periods=dict(historical_2026=recent,separate_2025_q4=older,separate_2025_q2=q2result),
        out_of_sample=False,independent_holdout_verified=False,execution_allowed=False,adoption_allowed=False,
        account_return_pct=None,account_max_dd_pct=None)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive_2026',type=Path);p.add_argument('archive_q4',type=Path)
    p.add_argument('archive_q2',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();v=run(a.archive_2026,a.archive_q4,a.archive_q2)
    with a.output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(v,stream,indent=2,allow_nan=False);stream.write('\n')
