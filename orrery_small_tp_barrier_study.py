# SPDX-License-Identifier: GPL-3.0-only
"""Small TP and barrier-only holding research, not a 95% win-rate forecast."""
from bisect import bisect_left
from collections import Counter
import gzip,json
from hashlib import sha256
from math import isfinite,sqrt
from pathlib import Path
from orrery_paired_archive_study import SOURCE_PINS,read_side,evaluate_plan,summary
from orrery_pattern_session_review import partition
from orrery_pattern_session_spread import widen
from orrery_pattern_robustness import PREENTRY,one_position
from orrery_pattern_entry_tradeability import load_stress_parent,ROOT

MODEL='PULLBACK_RESUME_FIXED_6'
TARGETS=(.05,.10,.25,1.5)
POLICIES=('FIXED_120','BARRIER_ONLY')
SPEC=dict(model=MODEL,fixed_sl_price=6,target_r=TARGETS,exit_policies=POLICIES,
          extra_spread_price_units=(0.,.3,.6),
          holding='BARRIER_ONLY has no time exit; ends unresolved at source end or unexplained gap.',
          quotes='BUY Ask entry/Bid exit; SELL Bid entry/Ask exit; no interpolation.',
          gap='Prior unauthenticated weekly closure scenario; actual reopening quotes; adverse SL beyond -1R retained.',
          same_minute='Both TP and SL touched -> ambiguous, never forced into a win.',
          cohorts='ALL and original frozen spread/SL/ATR100 PASS group; no new entry filter.',
          probability='Resolved-only Wilson interval assumes iid Bernoulli; overlap invalidates confidence interpretation.',
          independent_holdout=False,automatic_adoption=False)
FEATURE_STEM=ROOT/'research_evidence/local-history-20261101/pattern_entry_tradeability_20261103'
FEATURE_MANIFEST_SHA='976bd2a7fd1dce04f29d57dea7b9c4456ffb04af5db91f1c587e2662fd1b3211'
CORE=('entry_at','side','status','r','exit_at','exit_reason','entry','stop','target',
      'initial_risk_price','last_observed_until','stop_first_reference_r')


def wilson(w,n):
    if type(w) is not int or type(n) is not int or not 0<=w<=n:raise ValueError('Binomial counts required')
    if not n:return None
    z=1.959963984540054;p=w/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den;half=z*sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return dict(lower_pct=100*max(0,center-half),upper_pct=100*min(1,center+half),iid_assumption_verified=False)


def replay(plan,bid,ask,target_r,policy,*,times=None):
    if type(target_r) not in (int,float) or not isfinite(target_r) or target_r<=0 or policy not in POLICIES:
        raise ValueError('Explicit positive target and exit policy required')
    pre=evaluate_plan(plan,bid,ask,horizon=1)
    if pre['status'] in PREENTRY:return pre
    t=plan['first_poi_touch_close'];side=plan['side'];buy=side=='BUY'
    entry=ask[t]['open'] if buy else bid[t]['open'];risk=6.
    stop=entry+(-risk if buy else risk);target=entry+(target_r*risk if buy else -target_r*risk)
    exit_side=bid if buy else ask;times=times if times is not None else sorted(set(bid)&set(ask))
    deadline=t+120*60 if policy=='FIXED_120' else None
    stamp=t;last=None;skips=[]
    def out(status,**kw):return dict(entry_at=t,side=side,status=status,**kw)
    def resolved(stamp,price,reason,**kw):
        return out('RESOLVED_REFERENCE',r=(price-entry)/risk if buy else (entry-price)/risk,
                   exit_at=stamp,exit_reason=reason,entry=entry,stop=stop,target=target,initial_risk_price=risk,**kw)
    def censored(kind,**kw):
        extra={}
        if last is not None:
            p=exit_side[last]['close']
            extra=dict(last_known_close_at=last+60,last_known_close_reference_r=(p-entry)/risk if buy else (entry-p)/risk)
        return out('CENSORED_AT_SIDE_GAP',last_observed_until=stamp,gap_class=kind,
                   skipped_routine_gaps=skips.copy(),**extra,**kw)
    while True:
        reopened=False
        if stamp not in bid or stamp not in ask:
            i=bisect_left(times,stamp)
            if i==len(times):return censored('SOURCE_END')
            nxt=times[i]
            if nxt-stamp>8*86400:return censored('GAP_BUDGET')
            parts=partition(stamp,nxt)
            if set(parts)!={'ROUTINE_CLOSED_CANDIDATE'}:return censored('UNRESOLVED',gap_partition=parts)
            skips.append(dict(first_missing=stamp,reopen_at=nxt));stamp=nxt;reopened=True
        b=exit_side[stamp]
        if b['open']<=stop if buy else b['open']>=stop:return resolved(stamp,b['open'],'STOP_AT_OBSERVED_OPEN')
        if reopened and (b['open']>=target if buy else b['open']<=target):return resolved(stamp,target,'TP_TOUCH')
        if deadline is not None and stamp>=deadline:
            return resolved(stamp,b['open'],'TIMEOUT_CLOSE',timeout_deferred_to_reopen=True)
        sl=b['low']<=stop if buy else b['high']>=stop
        tp=b['high']>=target if buy else b['low']<=target
        if sl and tp:return out('AMBIGUOUS_SAME_MINUTE',exit_at=stamp,r=None,stop_first_reference_r=-1)
        if sl:return resolved(stamp,stop,'SL_TOUCH')
        if tp:return resolved(stamp,target,'TP_TOUCH')
        if deadline is not None and stamp+60==deadline:return resolved(deadline,b['close'],'TIMEOUT_CLOSE')
        last=stamp;stamp+=60


def metrics(rows):
    result=summary(rows);rs=[r['r'] for r in rows if r['status']=='RESOLVED_REFERENCE']
    wins=[r for r in rs if r>0];losses=[-r for r in rs if r<0]
    entered=[r for r in rows if r['status'] not in PREENTRY]
    uncertain=sum(r['status'] in ('CENSORED_AT_SIDE_GAP','AMBIGUOUS_SAME_MINUTE') for r in entered)
    result.update(mean_positive_r=sum(wins)/len(wins) if wins else None,
                  mean_negative_absolute_r=sum(losses)/len(losses) if losses else None,
                  max_negative_absolute_r=max(losses) if losses else None,
                  entered_plans=len(entered),unresolved_entered=uncertain,
                  positive_rate_bounds_all_entered_pct=[100*len(wins)/len(entered),100*(len(wins)+uncertain)/len(entered)] if entered else None,
                  resolved_only_iid_wilson95=wilson(len(wins),len(rs)),
                  exit_reason_counts=dict(Counter(r['exit_reason'] for r in rows if r['status']=='RESOLVED_REFERENCE')),
                  max_nominal_exit_bar_delay_minutes=max(((r['exit_at']-r['entry_at'])//60 for r in rows if r['status']=='RESOLVED_REFERENCE'),default=None))
    return result


def load_features():
    raw=Path(str(FEATURE_STEM)+'_manifest.json').read_bytes()
    if sha256(raw).hexdigest()!=FEATURE_MANIFEST_SHA:raise ValueError('Feature manifest changed')
    m=json.loads(raw);z=Path(str(FEATURE_STEM)+'.json.gz').read_bytes()
    if sha256(z).hexdigest()!=m['gzip_sha256']:raise ValueError('Feature archive changed')
    raw=gzip.decompress(z)
    if sha256(raw).hexdigest()!=m['uncompressed_sha256']:raise ValueError('Feature evidence changed')
    for name,pin in m['engine_code_sha256'].items():
        if sha256((ROOT/name).read_bytes()).hexdigest()!=pin:raise ValueError('Feature engine changed')
    return json.loads(raw)


def run(folder,stem):
    stress=load_stress_parent();features=load_features();base_bid={};base_ask={}
    for name,pin in SOURCE_PINS.items():
        rows,a=read_side(Path(folder)/name)
        if a['sha256']!=pin:raise ValueError('Source pin changed')
        dest=base_bid if name.startswith('bid_') else base_ask
        if set(rows)&set(dest):raise ValueError('Duplicate source clock')
        dest.update(rows)
    if set(base_bid)!=set(base_ask):raise ValueError('Exact paired source required')
    times=sorted(base_bid);results={};matches=0
    for delta in (0.,.3,.6):
        bid,ask=widen(base_bid,base_ask,delta)
        for window,models in stress['results'].items():
            prior=models[MODEL][str(delta)]['outcomes'];fs=features['models'][window][MODEL]['features']
            for tp in TARGETS:
                for policy in POLICIES:
                    rows=[]
                    for old in prior:
                        r=replay(dict(first_poi_touch_close=old['entry_at'],side=old['side']),bid,ask,tp,policy,times=times)
                        rows.append(dict(r,candidate_id=old['candidate_id']))
                    if tp==1.5 and policy=='FIXED_120':
                        project=lambda r:{k:r[k] for k in CORE if k in r}
                        if [project(r) for r in rows]!=[project(r) for r in prior]:raise ValueError('Original 120-minute 1.5R baseline changed')
                        matches+=1
                    passed=[r for r in rows if fs[r['candidate_id']]['group']=='PASS']
                    results.setdefault(window,[]).append(dict(target_r=tp,exit_policy=policy,extra_spread=delta,
                        all=metrics(rows),pass_cohort=metrics(passed),outcomes=rows,
                        pass_one_position=one_position(passed)))
    report=dict(status='SMALL_TP_VS_HOLD_UNTIL_BARRIER_RESEARCH',specification=SPEC,
        specification_sha256=sha256(json.dumps(SPEC,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        source_pins=SOURCE_PINS,feature_manifest_sha256=FEATURE_MANIFEST_SHA,results=results,case_count=48,
        six_original_120_minute_1_5r_price_outcomes_match=matches==6,
        engine_code_sha256={n:sha256((ROOT/n).read_bytes()).hexdigest() for n in
            ('orrery_small_tp_barrier_study.py','orrery_pattern_session_review.py','orrery_pattern_session_spread.py','orrery_pattern_entry_tradeability.py','orrery_pattern_robustness.py','orrery_paired_archive_study.py')},
        adopted=False,execution_allowed=False,out_of_sample=False,formal_lsr02=False,
        calibrated_win_probability=None,net_expectancy_r=None,account_return_pct=None,account_max_dd_usd=None,
        limitations=['M1 OHLC is data resolution, not a 1-minute holding limit or tick execution proof.',
                    'Small intraminute targets may be touched without guaranteed executable fills.',
                    'No time exit does not mean eventual profit: SL, gaps and source-end positions remain.',
                    'Weekly closure hypothesis unauthenticated; fees, swaps, further slippage and margin unknown.',
                    'Overlapping historical candidates are correlated; Wilson interval is an iid illustration only.',
                    'Frozen inspected M5 entry candidates; no new 1-minute signal or verified predictive model.'])
    raw=(json.dumps(report,indent=2,allow_nan=False)+'\n').encode();z=gzip.compress(raw,mtime=0)
    m=dict(gzip_sha256=sha256(z).hexdigest(),uncompressed_sha256=sha256(raw).hexdigest(),engine_code_sha256=report['engine_code_sha256'])
    p=Path(str(stem)+'.json.gz');q=Path(str(stem)+'_manifest.json')
    if p.exists() or q.exists():raise FileExistsError('New destinations required')
    with p.open('xb') as f:f.write(z)
    with q.open('x',encoding='utf-8') as f:json.dump(m,f,indent=2);f.write('\n')
    return report


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('stem',type=Path)
    a=p.parse_args();r=run(a.folder,a.stem)
    for w,cases in r['results'].items():
        print(w)
        for c in cases:
            if c['exit_policy']=='BARRIER_ONLY' and c['extra_spread']==.3:
                print(c['target_r'],json.dumps(dict(all=c['all'],passed=c['pass_cohort'])))
