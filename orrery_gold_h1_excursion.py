# SPDX-License-Identifier: GPL-3.0-only
"""Bounds on in-position MFE/MAE; never use post-exit prices as opportunities."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from math import isfinite
from statistics import mean, median

from orrery_gold_ab_archive_comparison import aggregate_complete
from orrery_gold_entry_routing import START as Q2_START, END as Q2_END, load as load_q2
from orrery_gold_h1_state import EVIDENCE, COST
from orrery_gold_h1_vhf_rising import replay_rising
from orrery_gold_nested_wave_october import complete_m5
from orrery_gold_pullback_study import START, END, load_archive
from orrery_gold_session_breakout import Q4_START, load_q4
from orrery_gold_session_hourly import signals, replay

LEVELS=(.25,.5,1,1.5,2)
EPS=1e-10


def reaches(value,level):
    return value>=level-EPS
CLOSE_EXITS={'TIMEOUT_CLOSE','SESSION_CLOSE','PERIOD_END_CLOSE'}


def excursion(row,bid,ask):
    if row['side'] not in ('BUY','SELL'):
        raise ValueError('Invalid excursion direction')
    at=row['at_utc'];buy=row['side']=='BUY';sign=1 if buy else -1
    result=dict(at_utc=at,side=row['side'],baseline_status=row['status'],
                baseline_exit_reason=row.get('exit_reason'),mfe_r_bounds=None,mae_r_bounds=None,
                full_trade_bounds_available=False,observed_mfe_r_bounds=None,observed_mae_r_bounds=None,
                realized_net_r=None,giveback_r_bounds=None)
    if at not in bid or at not in ask:
        return dict(result,coverage='NO_ENTRY_QUOTE')
    entry=(ask if buy else bid)[at]['open']
    stop=(bid if buy else ask)[at]['open']-sign*row['stop_distance']
    risk=sign*(entry-stop)
    if not isfinite(risk) or risk<=0:
        return dict(result,coverage='INVALID_ENTRY_RISK')
    resolved=row['status']=='RESOLVED_REFERENCE'
    reason=row.get('exit_reason')
    if resolved:
        if reason not in CLOSE_EXITS|{'SL_TOUCH','TP_TOUCH','STOP_AT_OBSERVED_OPEN'}:
            raise ValueError('Unsupported resolved exit')
        cutoff=row['exit_at']
        coverage='COMPLETE_TO_EXIT'
    elif row['status']=='CENSORED_AT_SIDE_GAP':
        cutoff=row['last_observed_until'];coverage='PARTIAL_TO_GAP'
    elif row['status']=='AMBIGUOUS_SAME_MINUTE':
        cutoff=row['exit_at'];coverage='AMBIGUOUS_EXIT'
    else:
        return dict(result,coverage='UNAVAILABLE_'+row['status'])
    if cutoff<at or (cutoff-at)%60:
        raise ValueError('Invalid excursion clock')
    exit_side=bid if buy else ask
    favorable=adverse=0.0
    def point(price):
        return sign*(price-entry)/risk
    # These complete bars precede an intrabar/open exit, or end exactly at a
    # timeout's close. No bar following a stop is included.
    for t in range(at,cutoff,60):
        if t not in bid or t not in ask:
            raise ValueError('Missing minute before claimed observation cutoff')
        bar=exit_side[t]
        favorable=max(favorable,point(bar['high'] if buy else bar['low']))
        adverse=max(adverse,-point(bar['low'] if buy else bar['high']))
    flo=fhi=favorable;alo=ahi=adverse
    if reason not in CLOSE_EXITS and coverage!='PARTIAL_TO_GAP':
        if cutoff not in bid or cutoff not in ask:
            raise ValueError('Terminal quote missing')
        bar=exit_side[cutoff]
        opening=point(bar['open'])
        # A TP at an observed gap-open is modeled at the fixed target by the
        # original engine. Cap excursion to that model exit as well.
        opening=min(2,opening)
        flo=max(flo,opening);alo=max(alo,-opening)
        if reason=='STOP_AT_OBSERVED_OPEN':
            flo=fhi=max(flo,row['r']);alo=ahi=max(alo,-row['r'])
        else:
            if resolved:
                terminal_r=2 if reason=='TP_TOUCH' else -1 if reason=='SL_TOUCH' else row['r']
                flo=max(flo,terminal_r);alo=max(alo,-terminal_r)
            fhi=max(flo,min(2,point(bar['high'] if buy else bar['low'])))
            ahi=max(alo,min(1,-point(bar['low'] if buy else bar['high'])))
    if abs(fhi-flo)<EPS: fhi=flo
    if abs(ahi-alo)<EPS: ahi=alo
    result.update(coverage=coverage,observed_mfe_r_bounds=[flo,fhi],observed_mae_r_bounds=[alo,ahi])
    if resolved:
        net=row['r']-COST/risk
        result.update(full_trade_bounds_available=True,mfe_r_bounds=[flo,fhi],mae_r_bounds=[alo,ahi],
                      realized_net_r=net,giveback_r_bounds=[max(0,flo-row['r']),max(0,fhi-row['r'])])
    return result


def summarize(rows):
    complete=[r for r in rows if r['full_trade_bounds_available']]
    partial=[r for r in rows if not r['full_trade_bounds_available']]
    def bounds(field,fn):
        return [fn(r[field][i] for r in complete) for i in (0,1)] if complete else None
    return dict(candidates=len(rows),coverage=dict(Counter(r['coverage'] for r in rows)),
        complete_to_exit=len(complete),incomplete=len(partial),
        mean_mfe_r_bounds=bounds('mfe_r_bounds',mean),median_mfe_r_bounds=bounds('mfe_r_bounds',median),
        mean_mae_r_bounds=bounds('mae_r_bounds',mean),mean_giveback_r_bounds=bounds('giveback_r_bounds',mean),
        thresholds={str(level):dict(
            confirmed_before_exit=sum(reaches(r['mfe_r_bounds'][0],level) for r in complete),
            terminal_minute_uncertain=sum(not reaches(r['mfe_r_bounds'][0],level) and reaches(r['mfe_r_bounds'][1],level) for r in complete),
            not_reached_before_exit=sum(not reaches(r['mfe_r_bounds'][1],level) for r in complete),
            incomplete_with_observed_reach=sum(r['observed_mfe_r_bounds'] is not None and
                reaches(r['observed_mfe_r_bounds'][0],level) for r in partial),
            incomplete_other=len(partial)-sum(r['observed_mfe_r_bounds'] is not None and
                reaches(r['observed_mfe_r_bounds'][0],level) for r in partial),
            resolved_losses_after_confirmed_reach=sum(reaches(r['mfe_r_bounds'][0],level) and
                r['realized_net_r']<0 for r in complete)) for level in LEVELS},
        mfe_includes_spread=True,additional_cost_in_mfe=False,
        alternative_exit_replayed=False,account_return_pct=None)


def analyze(bid,ask,m5,start,end,expected):
    found=list(signals(aggregate_complete(m5,3600),end,session=True))
    base,_=replay(found,bid,ask,end)
    rising,_=replay_rising(aggregate_complete(m5,3600),bid,ask,end)
    if {'BASELINE':base,'VHF_RISING':rising}!=expected:
        raise ValueError('Original full replay records did not reproduce')
    output={};records={}
    for name,rows in expected.items():
        records[name]=[excursion(row,bid,ask) for row in rows]
        output[name]=summarize(records[name])
    return dict(start_utc=start,end_utc_exclusive=end,baseline_reproduced=True,arms=output,records=records)


def run(current_root,prior_root,q2_root):
    raw=(EVIDENCE/'gold_h1_excursion_plan.json').read_bytes();plan=json.loads(raw)
    for name,expected in plan['files_sha256'].items():
        if sha256(Path(__file__).parent.joinpath(name).read_bytes()).hexdigest()!=expected:
            raise ValueError('Excursion input/code pin mismatch: '+name)
    original=json.loads((EVIDENCE/'gold_session_hourly_results.json').read_text())
    filtered=json.loads((EVIDENCE/'gold_h1_vhf_rising_results.json').read_text())
    q2=json.loads((EVIDENCE/'gold_h1_q2_results.json').read_text())
    periods={}
    bid,ask,m5,_,_,_=load_archive(current_root)
    expected=lambda key:dict(BASELINE=original[key]['records']['SESSION_HYPOTHESIS'],VHF_RISING=filtered[key]['records'])
    periods['historical_2026']=analyze(bid,ask,m5,START,END,expected('historical_2026'))
    bid,ask,_,_=load_q4(prior_root)
    m5=complete_m5({t:bid[t] for t in bid.keys() & ask.keys()},Q4_START,START)
    periods['separate_2025_q4']=analyze(bid,ask,m5,Q4_START,START,expected('separate_2025_q4'))
    bid,ask,m5,_=load_q2(q2_root)
    periods['separate_2025_q2']=analyze(bid,ask,m5,Q2_START,Q2_END,q2['records'])
    return dict(study='gold_h1_excursion_v1_1',periods=periods,plan_sha256=sha256(raw).hexdigest(),
        post_trade_diagnostic=True,out_of_sample=False,independent_holdout_verified=False,
        alternative_exit_replayed=False,execution_allowed=False,adoption_allowed=False,
        account_return_pct=None,account_max_dd_pct=None)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive_2026',type=Path);p.add_argument('archive_q4',type=Path)
    p.add_argument('archive_q2',type=Path);p.add_argument('output',type=Path)
    args=p.parse_args();result=run(args.archive_2026,args.archive_q4,args.archive_q2)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
