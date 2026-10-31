"""Confirmation entry vs retest waiting on ALL as-of VHF confirmations.
Same inspected public sample; no future-retouch selection of immediate entries.
No portfolio execution, broker proof or automatic parameter selection.
"""
import csv
import datetime as dt
import hashlib
import json
from collections import Counter
from pathlib import Path
from orrery_real_bars_lsr_bridge import load
from orrery_xau_hypothetical_pnl import simulate
from orrery_xau_structural_stop_comparison import stop_specs, SPREAD
from orrery_xau_h4_alignment import START, END, summarize


def entry_plans(confirmations, *, mode, observations=None, start=START, end=END):
    if any(type(t) is not int for t in (start,end)) or not 0<start<end:
        raise ValueError('Explicit integer cohort bounds required')
    if mode not in ('CONFIRMATION','RETEST'):
        raise ValueError('Unknown entry mode')
    plans=[];skips=[];seen=set()
    for c in confirmations:
        sweep,confirm,side=(c[k] for k in ('sweep_close','confirmation_close','side'))
        identity=(sweep,confirm,side)
        if type(sweep) is not int or type(confirm) is not int or not sweep<confirm or side not in ('BUY','SELL') or identity in seen:
            raise ValueError('Invalid or duplicate confirmation')
        seen.add(identity)
        entry=confirm
        if mode=='RETEST':
            o=observations[identity]
            entry=o['entry_at']
            if o['status']!='RETEST':
                skips.append(dict(candidate_id=identity,reason=o['status']))
                continue
            if type(entry) is not int or not confirm<entry<=confirm+3600:
                raise ValueError('Invalid retest time')
        if not start<=entry<end:
            skips.append(dict(candidate_id=identity,reason='OUTSIDE_ENTRY_WINDOW'))
            continue
        # Compatibility field denotes modeled entry, not a claimed POI touch.
        plans.append(dict(sweep_close=sweep,confirmation_close=confirm,side=side,
                          first_poi_touch_close=entry,candidate_id=identity,entry_rule=mode))
    if len({(p['first_poi_touch_close'],p['side']) for p in plans})!=len(plans):
        raise ValueError('Duplicate modeled entry identity; explicit allocation needed')
    return plans,skips


def run(root=Path('.')):
    source=root/'public_xau_sequence_report.json'
    seq=json.loads(source.read_text(encoding='utf-8'))
    universe=[c for c in seq['confirmation_evidence'] if START<=c['confirmation_close']<END]
    observations={}
    for o in seq['retest_observations']:
        key=(o['sweep_close'],o['confirmation_close'],o['side'])
        if key in observations:raise ValueError('Duplicate observation')
        observations[key]=o
    m1_path=root/'public_xau_bars/XAUUSD_M1_UNVERIFIED_QUOTE.csv'
    m15_path=root/'public_xau_bars/XAUUSD_M15_UNVERIFIED_QUOTE.csv'
    with m1_path.open(newline='',encoding='utf-8') as f:
        m1=[dict(at=int(dt.datetime.fromisoformat(r['timestamp_utc']).timestamp()),
                 high=float(r['bid_high']),low=float(r['bid_low'])) for r in csv.DictReader(f)]
    m15=load(m15_path,'M15')['bars']
    results={};by_candidate={}
    for mode in ('CONFIRMATION','RETEST'):
        plans,skips=entry_plans(universe,mode=mode,observations=observations)
        plan_path=root/('public_xau_'+mode.lower()+'_entry_plans.json')
        plan_path.write_text(json.dumps({'retouch_evidence':plans},indent=2)+'\n',encoding='utf-8')
        structural=stop_specs(plans,m15,m1,spread=SPREAD)
        annotations=[dict(entry_known_at=p['first_poi_touch_close'],side=p['side'],group='UNKNOWN') for p in plans]
        identities={(p['first_poi_touch_close'],p['side']):tuple(p['candidate_id']) for p in plans}
        for policy,stops in (('FIXED_6',None),('SWEEP_EXTREME',structural)):
            sim=simulate(m1_path,plan_path,reward_r=1.5,structural_stops=stops)
            label=mode+'_'+policy
            outcomes=sim['trades_detail']
            by_candidate[label]={identities[(t['touch_close_utc'],t['side'])]:t for t in outcomes}
            results[label]={'confirmation_universe':len(universe),'entry_plans':len(plans),
                            'no_entry_reasons':dict(Counter(x['reason'] for x in skips)),
                            'no_entry_details':skips,
                            'entry_outcomes':summarize(annotations,outcomes)['ALL'],
                            'stop_policy_skips':sim['skipped_stop_policy'],
                            'stop_policy_skip_counts':dict(Counter(x['reason'] for x in sim['skipped_stop_policy'])),
                            'incomplete_after_entry':sim['skipped_incomplete'],
                            'exit_reason_counts':dict(Counter(t['exit_reason'] for t in outcomes)),
                            'trades_detail':outcomes}
    # Descriptive hindsight attribution ONLY; never used to select immediate plans.
    attribution={}
    for policy in ('FIXED_6','SWEEP_EXTREME'):
        rows={}
        for status in sorted({observations[(c['sweep_close'],c['confirmation_close'],c['side'])]['status'] for c in universe}):
            subset=[c for c in universe if observations[(c['sweep_close'],c['confirmation_close'],c['side'])]['status']==status]
            annotations=[dict(entry_known_at=c['confirmation_close'],side=c['side'],group='UNKNOWN') for c in subset]
            keys={(c['sweep_close'],c['confirmation_close'],c['side']) for c in subset}
            outcomes=[t for k,t in by_candidate['CONFIRMATION_'+policy].items() if k in keys]
            rows[status]=summarize(annotations,outcomes)['ALL']
        attribution[policy]=rows
    paired={}
    for policy in ('FIXED_6','SWEEP_EXTREME'):
        a,b='CONFIRMATION_'+policy,'RETEST_'+policy
        common=set(by_candidate[a]) & set(by_candidate[b])
        paired[policy]={'same_confirmations_resolved_both':len(common),
                        'confirmation_mean_r':round(sum(by_candidate[a][k]['r'] for k in common)/len(common),4) if common else None,
                        'retest_mean_r':round(sum(by_candidate[b][k]['r'] for k in common)/len(common),4) if common else None,
                        'warning':'Supplementary future-resolved subset; not an unbiased immediate-entry strategy.'}
    out={'status':'ALL_CONFIRMATIONS_ENTRY_RULE_RESEARCH_NOT_ADOPTED',
         'cohort_basis':'confirmation_close in [2026-04-25,2026-09-25) UTC; both entry rules end at same horizon',
         'confirmation_universe':len(universe),'results':results,'paired_resolved_diagnostic':paired,
         'assumptions':{'spread_price_units':SPREAD,'reward_r':1.5,'exit_horizon_minutes':120,
                        'retest_wait_minutes':60,'h4_filter':False},
         'future_retest_attribution_NOT_AN_ENTRY_FILTER':attribution,
         'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,m1_path,m15_path)},
         'execution_allowed':False,'adopted':False,'out_of_sample':False,
         'warning':'All confirmations are recorded before observing retouch. Waiting can legitimately skip, expire or have unknown history; no-entry is not a zero-return trade. Same exit engine and stop policies, modeled next M1 open. Does not reproduce Kou or formal 2.6. Small inspected public mid-quote sample; broker Bid/Ask, fees, slippage, margin, portfolio overlap and account stops unverified/unmodeled. No 95% win-rate or account profit claim.'}
    (root/'public_xau_confirmation_entry_comparison.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({**out,'results':{k:{a:b for a,b in v.items() if a not in ('trades_detail','no_entry_details','stop_policy_skips')} for k,v in results.items()}}))
    return out

if __name__=='__main__':run()
