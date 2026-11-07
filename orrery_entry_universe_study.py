# SPDX-License-Identifier: GPL-3.0-only
"""Inspected-data exploration of all confirmations, not formal LSR02 or net PnL."""
from collections import Counter
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from lsr02_structure import detect
from lsr03_vhf import calculate
from orrery_public_xau_sequence_study import segments, observe_retest, report_from_bars
from orrery_real_bars_lsr_bridge import load
from orrery_xau_confirmation_entry_comparison import entry_plans
from orrery_xau_structural_stop_comparison import stop_specs
from orrery_xau_hypothetical_pnl import simulate
from orrery_xau_h4_alignment import START, END, summarize


def confirmations(m15, m5):
    events = {}
    for bars, step in ((m15,900),(m5,300)):
        rows=[]
        for group in segments(bars,step):
            if len(group)<8:continue
            for e in detect(group,as_of=group[-1]['close_time'],interval=step)['events']:
                if (step==900 and e['kind']=='SWEEP') or (step==300 and e['kind'] in ('BOS','CHoCH')):
                    rows.append(dict(e,segment_start=group[0]['close_time']))
        events[step]=rows
    used=set();out=[];groups=segments(m15,900)
    for sweep in sorted(events[900],key=lambda e:e['known_at']):
        at=sweep['known_at'];target='DOWN' if sweep['direction']=='UP' else 'UP'
        eligible=[(i,e) for i,e in enumerate(events[300]) if i not in used
                  and at<e['known_at']<=at+3600 and e['direction']==target
                  and e['segment_start']<=at<e['known_at']]
        if not eligible:continue
        i,e=min(eligible,key=lambda x:(x[1]['known_at'],x[0]));used.add(i)
        history=next(g for g in groups if g[0]['close_time']<=at<=g[-1]['close_time'])
        v=calculate([b for b in history if b['close_time']<=at],period=14,as_of=at,interval=900)
        out.append(dict(sweep_close=at,confirmation_close=e['known_at'],
                        side='BUY' if target=='UP' else 'SELL',poi=e.get('poi'),
                        vhf_at_sweep=v.get('value'),
                        vhf_pass=v['status']=='OK' and v['value']>=.4 and v['slope']=='RISING'))
    return out


def run(root):
    root=Path(root);bars=root/'public_xau_bars'
    raw_pin=sha256((root/'source.csv').read_bytes()).hexdigest()
    if raw_pin!='a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225':
        raise ValueError('Fixed raw source hash mismatch')
    m15=load(bars/'XAUUSD_M15_UNVERIFIED_QUOTE.csv','M15')['bars']
    m5=load(bars/'XAUUSD_M5_UNVERIFIED_QUOTE.csv','M5')['bars']
    all_rows=confirmations(m15,m5)
    original=report_from_bars(m15,m5)['confirmation_evidence']
    passed=[{k:v for k,v in c.items() if k!='vhf_pass'} for c in all_rows if c['vhf_pass']]
    if passed!=original:raise ValueError('Existing VHF candidate universe mismatch')
    universe=[c for c in all_rows if START<=c['confirmation_close']<END]
    observations={(c['sweep_close'],c['confirmation_close'],c['side']):observe_retest(c,m5) for c in universe}
    m1_path=bars/'XAUUSD_M1_UNVERIFIED_QUOTE.csv'
    with m1_path.open(newline='') as f:
        m1=[dict(at=int(datetime.fromisoformat(r['timestamp_utc']).timestamp()),high=float(r['bid_high']),low=float(r['bid_low'])) for r in csv.DictReader(f)]
    with m1_path.open(newline='') as f:
        minute_index={int(datetime.fromisoformat(r['timestamp_utc']).timestamp()):r for r in csv.DictReader(f)}
    results={}
    for scope,rows in (('ALL',universe),('VHF_PASS',[c for c in universe if c['vhf_pass']])):
        for mode in ('CONFIRMATION','RETEST'):
            plans,skips=entry_plans(rows,mode=mode,observations=observations)
            path=root/(scope+'_'+mode+'_plans.json');path.write_text(json.dumps(dict(retouch_evidence=plans)))
            annotations=[dict(entry_known_at=p['first_poi_touch_close'],side=p['side'],group='UNKNOWN') for p in plans]
            structural=stop_specs(plans,m15,m1,spread=.6)
            for policy,stops in (('FIXED_6',None),('SWEEP_EXTREME',structural)):
                sim=simulate(m1_path,path,reward_r=1.5,structural_stops=stops)
                results[scope+'_'+mode+'_'+policy]=dict(confirmation_universe=len(rows),entry_plans=len(plans),
                    no_entry_reasons=dict(Counter(x['reason'] for x in skips)),
                    entry_outcomes=summarize(annotations,sim['trades_detail'])['ALL'],
                    stop_policy_skip_counts=dict(Counter(x['reason'] for x in sim['skipped_stop_policy'])),
                    incomplete_after_entry=sim['skipped_incomplete'],
                    exit_reason_counts=dict(Counter(x['exit_reason'] for x in sim['trades_detail'])),
                    trades_detail=sim['trades_detail'])
    for v in results.values():
        trades=v['trades_detail'];monthly={};ambiguous=[];overlap_pairs=0
        for i,t in enumerate(trades):
            month=datetime.fromtimestamp(t['touch_close_utc'],timezone.utc).strftime('%Y-%m')
            monthly.setdefault(month,[]).append(t['r'])
            bar=minute_index.get(t['exit_time_utc'])
            if bar and t['exit_reason']=='STOP_INTRAMINUTE':
                high,low=float(bar['bid_high']),float(bar['bid_low'])
                both=(high>=t['target_assumed'] and low<=t['stop_assumed']) if t['side']=='BUY' else (low+.6<=t['target_assumed'] and high+.6>=t['stop_assumed'])
                if both:ambiguous.append(t['touch_close_utc'])
            overlap_pairs+=sum(a['touch_close_utc']<=t['exit_time_utc'] and t['touch_close_utc']<=a['exit_time_utc'] for a in trades[i+1:])
        v['monthly_resolved_only']={m:dict(resolved=len(rs),positive=sum(x>0 for x in rs),total_reference_r=round(sum(rs),5),mean_reference_r=round(sum(rs)/len(rs),5)) for m,rs in sorted(monthly.items())}
        v['same_minute_both_touch_stop_first_count']=len(ambiguous)
        v['potential_overlap_or_same_minute_boundary_pairs_resolved_only']=overlap_pairs
        v['further_cost_break_even_r_per_resolved_trade']=v['entry_outcomes']['mean_r']
        v['monthly_warning']='Descriptive inspected sample; months with no resolved trade omitted. Unknown outcomes remain unknown. Overlap uses minute lower-bound clocks, not verified concurrent exposure.'
    r=dict(status='EXPLORATORY_ALL_CONFIRMATIONS_NOT_FORMAL_LSR02',
        raw_source_sha256=raw_pin,
        study_code_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        period_utc='2026-04-25 inclusive to 2026-09-25 exclusive',
        full_source_confirmations=len(all_rows),full_source_vhf_passed=len(passed),
        original_vhf_universe_exact_match=True,
        assumptions=dict(spread_price_units=.6,reward_r=1.5,horizon_minutes=120,retest_minutes=60,h4_filter=False),
        results=results,source_hashes={p.name:sha256(p.read_bytes()).hexdigest() for p in bars.glob('*.csv')},
        out_of_sample=False,formal_lsr02=False,execution_allowed=False,adopted=False,
        net_expectancy_r=None,account_return_pct=None,account_max_dd_usd=None,
        warning='Known public OHLC; synthetic spread; same-minute both touches use stop-first, not observed intrabar sequence. Costs, overlap, account stops and margin unverified. No strategy selection or account profitability claim.')
    (root/'entry_universe_results.json').write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k!='results'}))
    print(json.dumps({k:{a:b for a,b in v.items() if a!='trades_detail'} for k,v in results.items()}))
    return r

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);run(p.parse_args().root)
