# SPDX-License-Identifier: GPL-3.0-only
"""One fixed 0.5R target alternative; full occupation replay, no adoption."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from orrery_gold_ab_archive_comparison import aggregate_complete
from orrery_gold_entry_routing import START as Q2_START, END as Q2_END, load as load_q2
from orrery_gold_h1_state import EVIDENCE, describe, features
from orrery_gold_nested_wave_october import complete_m5
from orrery_gold_pullback_study import START, END, load_archive, evaluate_pullback
from orrery_gold_session_breakout import Q4_START, load_q4
from orrery_gold_session_hourly import HORIZON, chains, signals, open_horizon


def candidates(h1,bid,ask,end):
    raw={r['at_utc']:r for r in signals(h1,end,session=True)}
    for window in chains(h1,session=True):
        at=window[-1]['close_time']
        if at in raw:
            f=features(window,raw[at],bid[at]['open'] if at in bid else None,ask[at]['open'] if at in ask else None)
            if f['vhf14_slope']=='RISING':yield raw[at]


def replay_target(found,bid,ask,end,target_r):
    if target_r not in (.5,2):raise ValueError('Only the fixed comparator and alternative are allowed')
    available=0;rows=[];skips={}
    for signal in found:
        at=signal['at_utc']
        why='OCCUPIED_OR_UNKNOWN_OUTCOME' if at<available else None
        horizon=open_horizon(at,end)
        if why is None and horizon==0:why='CLOSED_OR_PERIOD_END'
        if why:
            skips[why]=skips.get(why,0)+1;continue
        if at not in bid or at not in ask:
            rows.append(dict(signal,status='UNKNOWN_ENTRY_HISTORY'));continue
        buy=signal['side']=='BUY';sign=1 if buy else -1
        entry=(ask if buy else bid)[at]['open']
        stop=(bid if buy else ask)[at]['open']-sign*signal['stop_distance']
        result=evaluate_pullback(dict(first_poi_touch_close=at,side=signal['side']),bid,ask,
            structural_stop=stop,structural_known_at=at,target_price=entry+target_r*(entry-stop),horizon=horizon)
        if result['status']=='RESOLVED_REFERENCE':
            if result['exit_reason']=='TIMEOUT_CLOSE' and horizon<HORIZON:
                result['exit_reason']='PERIOD_END_CLOSE' if at+horizon*60==end else 'SESSION_CLOSE'
            available=result['exit_at']+(0 if result['exit_reason'] in ('TIMEOUT_CLOSE','SESSION_CLOSE','PERIOD_END_CLOSE') else 60)
        elif result['status'] in ('CENSORED_AT_SIDE_GAP','AMBIGUOUS_SAME_MINUTE'):
            available=at+horizon*60
        rows.append(dict(signal,horizon_minutes=horizon,**result))
    return rows,skips


def measure(bid,ask,m5,start,end,expected):
    found=list(candidates(aggregate_complete(m5,3600),bid,ask,end))
    baseline,skips=replay_target(found,bid,ask,end,2)
    if baseline!=expected:raise ValueError('2R comparator records changed')
    half,half_skips=replay_target(found,bid,ask,end,.5)
    old_clocks={r['at_utc'] for r in baseline}
    months=sorted({datetime.fromtimestamp(t,timezone.utc).strftime('%Y-%m') for t in range(start,end,86400)})
    return dict(baseline_reproduced=True,passing_signals=len(found),entries_absent_from_2r=sum(r['at_utc'] not in old_clocks for r in half),
        arms={name:dict(describe(rows),skipped=skip,by_utc_month={m:describe([r for r in rows if
            datetime.fromtimestamp(r['at_utc'],timezone.utc).strftime('%Y-%m')==m]) for m in months})
            for name,rows,skip in (('TP_2R',baseline,skips),('TP_05R',half,half_skips))},
        records=dict(TP_2R=baseline,TP_05R=half))


def run(current,prior,q2root):
    raw=(EVIDENCE/'gold_h1_half_target_plan.json').read_bytes();plan=json.loads(raw)
    for name,expected in plan['files_sha256'].items():
        if sha256(Path(__file__).parent.joinpath(name).read_bytes()).hexdigest()!=expected:
            raise ValueError('Half-target plan mismatch: '+name)
    original=json.loads((EVIDENCE/'gold_h1_vhf_rising_results.json').read_text())
    q2=json.loads((EVIDENCE/'gold_h1_q2_results.json').read_text())
    bid,ask,m5,_,_,_=load_archive(current)
    recent=measure(bid,ask,m5,START,END,original['historical_2026']['records'])
    bid,ask,_,_=load_q4(prior)
    m5=complete_m5({t:bid[t] for t in bid.keys() & ask.keys()},Q4_START,START)
    older=measure(bid,ask,m5,Q4_START,START,original['separate_2025_q4']['records'])
    bid,ask,m5,_=load_q2(q2root)
    q2result=measure(bid,ask,m5,Q2_START,Q2_END,q2['records']['VHF_RISING'])
    return dict(study='gold_h1_half_target_v1',periods=dict(historical_2026=recent,separate_2025_q4=older,separate_2025_q2=q2result),
        plan_sha256=sha256(raw).hexdigest(),hypotheses_replayed=1,hypothesis_selected_after_excursion_diagnostic=True,
        out_of_sample=False,execution_allowed=False,adoption_allowed=False,account_return_pct=None,account_max_dd_pct=None)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive_2026',type=Path);p.add_argument('archive_q4',type=Path)
    p.add_argument('archive_q2',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();v=run(a.archive_2026,a.archive_q4,a.archive_q2)
    with a.output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(v,stream,indent=2,allow_nan=False);stream.write('\n')
