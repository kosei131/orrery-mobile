# SPDX-License-Identifier: GPL-3.0-only
"""Descriptive inspected-data spread replay and concentration diagnostics."""
from collections import Counter
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from orrery_entry_universe_study import confirmations
from orrery_public_xau_sequence_study import observe_retest
from orrery_real_bars_lsr_bridge import load
from orrery_xau_confirmation_entry_comparison import entry_plans
from orrery_xau_structural_stop_comparison import stop_specs
from orrery_xau_hypothetical_pnl import simulate
from orrery_xau_h4_alignment import START, END, summarize
from orrery_xau_tp_stability_split import CUT

EVIDENCE = Path(__file__).resolve().parent/'research_evidence/local-history-20261101/entry_universe_profitability_20261102.json'
EVIDENCE_SHA256 = 'd298984ce96981f63cddad50886217de530431a78c1b8b50f1f4ba60e35a21dd'
SPREADS = (.6,1.2,2.0)


def stats(rows):
    values=[t['r'] for t in rows]
    if any(type(v) not in (int,float) or not isfinite(v) for v in values):
        raise ValueError('Finite reference R required')
    positive=sum(v for v in values if v>0);negative=-sum(v for v in values if v<0)
    return dict(resolved=len(values),positive=sum(v>0 for v in values),
        positive_rate_pct=round(100*sum(v>0 for v in values)/len(values),4) if values else None,
        total_reference_r=round(sum(values),5) if values else None,
        mean_reference_r=round(sum(values)/len(values),5) if values else None,
        pf_reference=round(positive/negative,5) if negative else None)


def stability(rows):
    monthly={}
    for t in rows:
        month=datetime.fromtimestamp(t['touch_close_utc'],timezone.utc).strftime('%Y-%m')
        monthly.setdefault(month,[]).append(t)
    winner_order=sorted((i for i,t in enumerate(rows) if t['r']>0),key=lambda i:(-rows[i]['r'],i))
    removals={}
    for n in (1,2,3):
        removed=set(winner_order[:n])
        removals[str(n)]=dict(removed_positive_trades=len(removed),
            remaining=stats([t for i,t in enumerate(rows) if i not in removed]))
    best=max(sorted(monthly),key=lambda m:sum(t['r'] for t in monthly[m])) if monthly else None
    return dict(all_resolved=stats(rows),
        split_utc=datetime.fromtimestamp(CUT,timezone.utc).isoformat(),
        before_cut=stats([t for t in rows if t['touch_close_utc']<CUT]),
        from_cut=stats([t for t in rows if t['touch_close_utc']>=CUT]),
        monthly={m:stats(v) for m,v in sorted(monthly.items())},
        remove_top_positive_trades=removals,best_month=best,
        excluding_best_month=stats([t for t in rows if datetime.fromtimestamp(t['touch_close_utc'],timezone.utc).strftime('%Y-%m')!=best]),
        out_of_sample=False,scope='RESOLVED_ONLY_NO_UNKNOWN_OUTCOME_IMPUTATION')


def run(root, output):
    root=Path(root);bars=root/'public_xau_bars'
    raw=EVIDENCE.read_bytes()
    if sha256(raw).hexdigest()!=EVIDENCE_SHA256:raise ValueError('Prior evidence changed')
    old=json.loads(raw)
    for name,pin in old['source_hashes'].items():
        if sha256((bars/name).read_bytes()).hexdigest()!=pin:raise ValueError('Normalized source changed')
    if sha256((root/'source.csv').read_bytes()).hexdigest()!=old['raw_source_sha256']:
        raise ValueError('Raw source changed')
    m1_path=bars/'XAUUSD_M1_UNVERIFIED_QUOTE.csv'
    m15=load(bars/'XAUUSD_M15_UNVERIFIED_QUOTE.csv','M15')['bars']
    m5=load(bars/'XAUUSD_M5_UNVERIFIED_QUOTE.csv','M5')['bars']
    universe=[c for c in confirmations(m15,m5) if START<=c['confirmation_close']<END]
    observations={(c['sweep_close'],c['confirmation_close'],c['side']):observe_retest(c,m5) for c in universe}
    with m1_path.open(newline='') as f:
        m1=[dict(at=int(datetime.fromisoformat(r['timestamp_utc']).timestamp()),high=float(r['bid_high']),low=float(r['bid_low'])) for r in csv.DictReader(f)]
    results={}
    for scope,rows in (('ALL',universe),('VHF_PASS',[c for c in universe if c['vhf_pass']])):
        for mode in ('CONFIRMATION','RETEST'):
            plans,skips=entry_plans(rows,mode=mode,observations=observations)
            path=root/('stability_'+scope+'_'+mode+'_plans.json')
            path.write_text(json.dumps(dict(retouch_evidence=plans)))
            annotations=[dict(entry_known_at=p['first_poi_touch_close'],side=p['side'],group='UNKNOWN') for p in plans]
            for spread in SPREADS:
                stops=stop_specs(plans,m15,m1,spread=spread)
                for policy,spec in (('FIXED_6',None),('SWEEP_EXTREME',stops)):
                    label=scope+'_'+mode+'_'+policy
                    sim=simulate(m1_path,path,spread_usd=spread,reward_r=1.5,structural_stops=spec)
                    out=dict(spread_price_units=spread,confirmation_universe=len(rows),entry_plans=len(plans),
                        no_entry_reasons=dict(Counter(x['reason'] for x in skips)),
                        entry_outcomes=summarize(annotations,sim['trades_detail'])['ALL'],
                        stop_policy_skip_counts=dict(Counter(x['reason'] for x in sim['skipped_stop_policy'])),
                        incomplete_after_entry=sim['skipped_incomplete'],
                        exit_reason_counts=dict(Counter(x['exit_reason'] for x in sim['trades_detail'])),
                        stability=stability(sim['trades_detail']),
                        trades_detail_sha256=sha256(json.dumps(sim['trades_detail'],sort_keys=True,separators=(',',':')).encode()).hexdigest())
                    if spread==.6:
                        prior=old['results'][label]
                        for key in ('confirmation_universe','entry_plans','no_entry_reasons','entry_outcomes',
                                    'stop_policy_skip_counts','incomplete_after_entry','exit_reason_counts'):
                            if out[key]!=prior[key]:raise ValueError('Prior baseline changed: '+label+' '+key)
                        if sim['trades_detail']!=prior['trades_detail']:raise ValueError('Prior individual trades changed')
                    results.setdefault(label,{})[str(spread)]=out
    report=dict(status='INSPECTED_DATA_SPREAD_REPLAY_AND_STABILITY_NOT_OOS',
        prior_evidence_sha256=EVIDENCE_SHA256,raw_source_sha256=old['raw_source_sha256'],
        source_hashes=old['source_hashes'],baseline_all_eight_models_exact_match=True,
        code_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),models=results,
        scenarios=24,spread_values_price_units=SPREADS,period_utc=old['period_utc'],
        observed_at_utc=datetime.now(timezone.utc).isoformat(),execution_allowed=False,adopted=False,
        out_of_sample=False,formal_lsr02=False,net_expectancy_r=None,account_return_pct=None,account_max_dd_usd=None,
        assumptions=dict(reward_r=1.5,horizon_minutes=120,retest_wait_minutes=60,h4_filter=False),
        limitations=['Same inspected public quote history; synthetic bid/ask, not actual broker spreads.',
            'Costs other than assumed spread unknown. No account margin, exposure, stops or net-profit claim.',
            'Each spread changes entries, exits, structural stop validity and observed outcome population.',
            'Winner/month removal is post-hoc sensitivity, not an implementable entry filter.',
            'Resolved-only returns omit unknown outcomes; no-entry is not a zero-return trade.'])
    with Path(output).open('x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({name:{s:case['entry_outcomes'] for s,case in values.items()} for name,values in results.items()}))
    return report

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();run(a.root,a.output)
