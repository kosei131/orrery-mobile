"""Same existing sweep/VHF candidates: fixed SL versus as-of sweep invalidation.
No threshold tuning, no broker fills or order authority.
"""
import csv
import datetime as dt
import hashlib
import json
from bisect import bisect_left
from pathlib import Path
from orrery_real_bars_lsr_bridge import load
from orrery_xau_hypothetical_pnl import simulate
from orrery_xau_h4_alignment import START, END, summarize

SPREAD = .6

def stop_specs(candidates, m15, m1, *, spread):
    lookup={b['close_time']:b for b in m15}
    times=[b['at'] for b in m1]
    if any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError('Nonincreasing M1 history')
    specs={}
    for c in candidates:
        sweep,confirm,entry,side=(c[k] for k in ('sweep_close','confirmation_close','first_poi_touch_close','side'))
        if not sweep<confirm<=entry or side not in ('BUY','SELL'):
            raise ValueError('Invalid candidate chronology/side')
        b=lookup[sweep]
        quote=b['low'] if side=='BUY' else b['high']
        price=quote if side=='BUY' else quote+spread
        a,z=bisect_left(times,sweep),bisect_left(times,entry)
        known=m1[a:z]
        reason=None
        # Every M1 after sweep close and BEFORE entry must be observed.
        if ([x['at'] for x in known]!=list(range(sweep,entry,60))):
            reason='UNKNOWN_PRE_ENTRY_HISTORY'
        elif any(x['low']<=quote if side=='BUY' else x['high']>=quote for x in known):
            reason='STRUCTURE_BREACHED_BEFORE_ENTRY'
        key=(entry,side)
        if key in specs:
            raise ValueError('Duplicate candidate')
        specs[key]={'price':price,'known_at':sweep,'blocked_reason':reason}
    return specs


def run(root=Path('.')):
    m1_path=root/'public_xau_bars/XAUUSD_M1_UNVERIFIED_QUOTE.csv'
    m15_path=root/'public_xau_bars/XAUUSD_M15_UNVERIFIED_QUOTE.csv'
    candidate_path=root/'public_xau_sequence_report.json'
    candidates=json.loads(candidate_path.read_text(encoding='utf-8'))['retouch_evidence']
    candidates=[c for c in candidates if START<=c['first_poi_touch_close']<END]
    with m1_path.open(newline='',encoding='utf-8') as f:
        m1=[{'at':int(dt.datetime.fromisoformat(r['timestamp_utc']).timestamp()),
             'high':float(r['bid_high']),'low':float(r['bid_low'])} for r in csv.DictReader(f)]
    specs=stop_specs(candidates,load(m15_path,'M15')['bars'],m1,spread=SPREAD)
    # Reuse the same simulator; no duplicate fill engine.
    # Full file contains earlier candidates: use a separate, explicit window file.
    window=root/'public_xau_stop_candidates.json'
    window.write_text(json.dumps({'retouch_evidence':candidates},indent=2)+'\n',encoding='utf-8')
    fixed=simulate(m1_path,window,reward_r=1.5)
    structural=simulate(m1_path,window,reward_r=1.5,structural_stops=specs)
    def key(t): return (t['touch_close_utc'],t['side'])
    common=set(map(key,fixed['trades_detail'])) & set(map(key,structural['trades_detail']))
    annotations=[{'entry_known_at':c['first_poi_touch_close'],'side':c['side'],'group':'UNKNOWN'} for c in candidates]
    paired_annotations=[a for a in annotations if (a['entry_known_at'],a['side']) in common]
    results={}
    for name,sim in [('FIXED_6',fixed),('SWEEP_EXTREME',structural)]:
        trades=sim['trades_detail']
        results[name]={'all_candidates':summarize(annotations,trades)['ALL'],
                       'paired_resolved_only':summarize(paired_annotations,[t for t in trades if key(t) in common])['ALL'],
                       'stop_policy_skips':sim['skipped_stop_policy'],
                       'incomplete_after_entry':sim['skipped_incomplete'],
                       'trades_detail':trades}
    report={'status':'SAME_CANDIDATE_STRUCTURAL_SL_RESEARCH',
            'period_utc':'2026-04-25 to 2026-09-25 exclusive',
            'assumptions':{'spread_price_units':SPREAD,'target_r':1.5,'timeout_minutes':120,
                           'structural_anchor':'confirmed M15 sweep candle extreme; zero padding',
                           'sell_stop_basis':'source high plus assumed spread, synthetic Ask trigger',
                           'stop_open_gaps':'observed worse opening price; SL not clamped to -1R'},
            'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (m1_path,m15_path,candidate_path)},
            'results':results,'execution_allowed':False,'broker_verified':False,'adopted':False,
            'warning':'Inspected public mid-quote OHLC, synthetic Bid/Ask. Fixed-R TP is a comparison benchmark, not 2.6. No structural stop padding calibrated to broker ticks; fees, slippage, margin and portfolio loss stops absent. Paired resolved subset can be selection biased; all candidates and policy skips retained. No account profit claim.'}
    (root/'public_xau_structural_stop_comparison.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({**report,'results':{k:{a:b for a,b in v.items() if a!='trades_detail'} for k,v in results.items()}}))
    return report

if __name__=='__main__': run()
