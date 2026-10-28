"""Fixed-candidate entry-delay and horizon sensitivity, never automatic tuning."""
import csv
import datetime as dt
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import median
from orrery_real_bars_lsr_bridge import load
from orrery_xau_hypothetical_pnl import simulate
from orrery_xau_structural_stop_comparison import stop_specs, SPREAD
from orrery_xau_h4_alignment import START, END, summarize

HORIZONS=(60,120,240)

def timing(candidates, quotes):
    rows=[]
    seen=set()
    for c in candidates:
        sweep,confirm,entry,side=(c[k] for k in ('sweep_close','confirmation_close','first_poi_touch_close','side'))
        if (any(type(t) is not int for t in (sweep,confirm,entry)) or
                not sweep<confirm<entry or side not in ('BUY','SELL') or (entry,side) in seen):
            raise ValueError('Invalid/duplicate candidate timing')
        seen.add((entry,side))
        drift=None
        if confirm in quotes and entry in quotes:
            drift=(quotes[entry]-quotes[confirm])*(1 if side=='BUY' else -1)
        rows.append({'entry_known_at':entry,'side':side,'group':'UNKNOWN',
                     'sweep_to_entry_minutes':(entry-sweep)/60,
                     'confirmation_to_entry_minutes':(entry-confirm)/60,
                     'directional_quote_drift_since_confirmation':drift,
                     'delay_cohort':'LE_15_MIN' if entry-confirm<=900 else 'GT_15_MIN'})
    return rows


def run(root=Path('.')):
    m1_path=root/'public_xau_bars/XAUUSD_M1_UNVERIFIED_QUOTE.csv'
    m15_path=root/'public_xau_bars/XAUUSD_M15_UNVERIFIED_QUOTE.csv'
    source=root/'public_xau_sequence_report.json'
    candidates=json.loads(source.read_text(encoding='utf-8'))['retouch_evidence']
    candidates=[c for c in candidates if START<=c['first_poi_touch_close']<END]
    m1=[];quotes={}
    with m1_path.open(newline='',encoding='utf-8') as f:
        for r in csv.DictReader(f):
            t=int(dt.datetime.fromisoformat(r['timestamp_utc']).timestamp())
            m1.append({'at':t,'high':float(r['bid_high']),'low':float(r['bid_low'])})
            quotes[t]=float(r['bid_open'])
    annotations=timing(candidates,quotes)
    specs=stop_specs(candidates,load(m15_path,'M15')['bars'],m1,spread=SPREAD)
    window=root/'public_xau_stop_candidates.json'
    # Same explicit window evidence as the SL comparison; no outcome selection.
    window.write_text(json.dumps({'retouch_evidence':candidates},indent=2)+'\n',encoding='utf-8')
    results={}
    def key(t):return (t['touch_close_utc'],t['side'])
    for policy,stops in (('FIXED_6',None),('SWEEP_EXTREME',specs)):
        sims={h:simulate(m1_path,window,reward_r=1.5,horizon_mins=h,structural_stops=stops) for h in HORIZONS}
        common=set.intersection(*(set(map(key,s['trades_detail'])) for s in sims.values()))
        common_annotations=[a for a in annotations if (a['entry_known_at'],a['side']) in common]
        horizons={}
        for h,s in sims.items():
            trades=s['trades_detail']
            cohorts={cohort:summarize([a for a in annotations if a['delay_cohort']==cohort],
                         [t for t in trades if key(t) in {(a['entry_known_at'],a['side']) for a in annotations if a['delay_cohort']==cohort}])['ALL']
                     for cohort in ('LE_15_MIN','GT_15_MIN')}
            horizons[str(h)]={'all_candidates':summarize(annotations,trades)['ALL'],
                             'common_resolved_across_horizons':summarize(common_annotations,[t for t in trades if key(t) in common])['ALL'],
                             'exit_reason_counts':dict(Counter(t['exit_reason'] for t in trades)),
                             'stop_policy_skips':s['skipped_stop_policy'],
                             'incomplete_after_entry':s['skipped_incomplete'],
                             'delay_cohorts':cohorts,'trades_detail':trades}
        results[policy]=horizons
    delays=[a['confirmation_to_entry_minutes'] for a in annotations]
    report={'status':'ENTRY_DELAY_AND_HORIZON_DIAGNOSTIC_NOT_OPTIMIZATION',
            'period_utc':'2026-04-25 to 2026-09-25 exclusive',
            'horizons_minutes':HORIZONS,'target_r':1.5,'spread_price_units':SPREAD,
            'candidate_timing':annotations,
            'confirmation_to_entry_minutes':{'minimum':min(delays) if delays else None,
                'median':median(delays) if delays else None,'maximum':max(delays) if delays else None},
            'results':results,'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (m1_path,m15_path,source)},
            'adopted':False,'automatic_horizon_selection':False,'execution_allowed':False,
            'warning':'All data inspected, small sample. Delays are descriptive, not proof that earlier fills were possible. Positive directional quote drift means price advanced in trade direction before assumed entry; source quote is not verified Bid/Ask. Intraminute exit timestamp is a lower boundary, not tick time. Longer horizons can censor different candidates; common subset remains selection biased. Same assumed costs, missing broker fees/slippage/margin. No account profit or 2.6-method claim.'}
    (root/'public_xau_entry_exit_diagnostic.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({**report,'candidate_timing_count':len(annotations),'candidate_timing':None,
                     'results':{p:{h:{k:v for k,v in row.items() if k not in ('trades_detail','delay_cohorts','stop_policy_skips')} for h,row in hrs.items()} for p,hrs in results.items()}}))
    return report

if __name__=='__main__':run()
