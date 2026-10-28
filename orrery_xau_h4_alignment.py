"""As-of H4 regime attribution of existing public XAU hypotheses.
Not Type A/B certification, optimization, broker returns or order permission.
"""
import datetime as dt
import hashlib
import json
from bisect import bisect_right
from collections import Counter
from pathlib import Path
from lsr02_regime import classify
from orrery_real_bars_lsr_bridge import load
from orrery_xau_hypothetical_pnl import simulate

# Fixed before this diagnostic run; not fitted to these outcomes.
CONFIG = dict(lookback=12, trend_efficiency=.3, range_efficiency=.2)
START = int(dt.datetime(2026,4,25,tzinfo=dt.timezone.utc).timestamp())
END = int(dt.datetime(2026,9,25,tzinfo=dt.timezone.utc).timestamp())
SOURCES = {'LSR_VHF':'public_xau_sequence_report.json',
           'M15_DIRECT':'public_xau_m15_breakout_candidates.json',
           'M15_RETEST':'public_xau_m15_retest_candidates.json'}

def annotate(h4, candidates, *, config, full_structure_history=False):
    if type(full_structure_history) is not bool:
        raise ValueError('Explicit boolean history mode required')
    scope = 'CONTIGUOUS_HISTORY' if full_structure_history else 'WINDOW'
    times = [b['close_time'] for b in h4]
    if any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError('H4 timestamps must strictly increase')
    # Validate parameters even for zero candidates.
    classify([], as_of=0, interval=14400, structure_scope=scope, **config)
    seen = set()
    rows = []
    for c in candidates:
        t, side = c['first_poi_touch_close'], c['side']
        if type(t) is not int or side not in ('BUY','SELL') or (t,side) in seen:
            raise ValueError('Invalid or duplicate candidate identity')
        seen.add((t,side))
        i = bisect_right(times,t)
        begin = i
        # Never bridge missing grid bars, weekends, or unverified holidays.
        while begin>0 and (full_structure_history or i-begin<config['lookback']):
            if begin<i and times[begin]-times[begin-1]!=14400:
                break
            begin-=1
        known = h4[begin:i]
        r = classify(known, as_of=t, interval=14400, structure_scope=scope, **config)
        direction = 'UP' if side=='BUY' else 'DOWN'
        group = ('ALIGNED' if r['regime']==direction else
                 'OPPOSED' if r['regime'] in ('UP','DOWN') else
                 'RANGE' if r['regime']=='RANGE_CANDIDATE' else 'UNKNOWN')
        rows.append({'entry_known_at':t, 'side':side, 'group':group,
                     'h4_regime':r['regime'], 'reason':r['reason'],
                     'h4_last_close':known[-1]['close_time'] if known else None,
                     'h4_bars_used':len(known), 'structure_scope':scope, 'execution_allowed':False})
    return rows


def summarize(annotations, outcomes):
    by_key = {}
    for trade in outcomes:
        key = (trade['touch_close_utc'],trade['side'])
        if key in by_key:
            raise ValueError('Duplicate outcome')
        by_key[key] = trade
    keys = {(a['entry_known_at'],a['side']) for a in annotations}
    if not set(by_key)<=keys:
        raise ValueError('Outcome without candidate')
    result = {}
    for name in ('ALL','ALIGNED','OPPOSED','RANGE','UNKNOWN'):
        selected = [a for a in annotations if name=='ALL' or a['group']==name]
        trades = [by_key[(a['entry_known_at'],a['side'])] for a in selected
                  if (a['entry_known_at'],a['side']) in by_key]
        values = [x['r'] for x in trades]
        profit = sum(x for x in values if x>0)
        loss = -sum(x for x in values if x<0)
        result[name] = {'candidates':len(selected),'resolved_outcomes':len(values),
                        'unresolved_or_unmodeled':len(selected)-len(values),
                        'wins':sum(x>0 for x in values),
                        'win_rate_pct':round(100*sum(x>0 for x in values)/len(values),2) if values else None,
                        'mean_r':round(sum(values)/len(values),4) if values else None,
                        'total_r':round(sum(values),4) if values else None,
                        'pf':round(profit/loss,4) if loss else None}
    return result


def run(root=Path('.')):
    folder = root/'public_xau_session_coverage'
    evidence = json.loads((folder/'report.json').read_text(encoding='utf-8'))
    if evidence['h4_aggregation'] is None or evidence['quotes_during_published_closure']:
        raise ValueError('Session crosscheck blocked H4 export')
    m1 = root/'public_xau_bars/XAUUSD_M1_UNVERIFIED_QUOTE.csv'
    if hashlib.sha256(m1.read_bytes()).hexdigest()!=evidence['normalized_m1_sha256']:
        raise ValueError('M1 changed since session crosscheck')
    h4_path = folder/'H4_WEEKLY_SCHEDULE_UNVERIFIED.csv'
    if hashlib.sha256(h4_path.read_bytes()).hexdigest()!=evidence['h4_file_sha256']:
        raise ValueError('H4 changed since session crosscheck')
    h4 = load(h4_path,'H4')['bars']
    results = {}
    for model, filename in SOURCES.items():
        path = root/filename
        candidates = json.loads(path.read_text(encoding='utf-8'))['retouch_evidence']
        candidates = [c for c in candidates if START<=c['first_poi_touch_close']<END]
        annotations = annotate(h4,candidates,config=CONFIG)
        # Reuse unchanged 1.5R/6-price-unit stop/0.6 spread research model.
        outcomes = simulate(m1,path,reward_r=1.5)['trades_detail']
        outcomes = [t for t in outcomes if START<=t['touch_close_utc']<END]
        expanded = annotate(h4,candidates,config=CONFIG,full_structure_history=True)
        transitions = Counter(a['reason']+' -> '+b['reason'] for a,b in zip(annotations,expanded))
        results[model] = {'groups':summarize(annotations,outcomes),'annotations':annotations,
                          'full_contiguous_structure_diagnostic': {
                              'groups':summarize(expanded,outcomes),
                              'regime_reason_counts':dict(Counter(a['reason'] for a in expanded)),
                              'reason_transitions':dict(transitions),
                              'annotations':expanded,
                              'adopted':False},
                          'regime_reason_counts':dict(Counter(a['reason'] for a in annotations)),
                          'candidate_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    report = {'status':'ASOF_H4_ALIGNMENT_ATTRIBUTION_ONLY',
              'period_utc':'2026-04-25 to 2026-09-25 exclusive','regime_parameters':CONFIG,
              'pivot_parameters':{'left':2,'right':2},
              'normalized_m1_sha256':evidence['normalized_m1_sha256'],
              'h4_file_sha256':hashlib.sha256(h4_path.read_bytes()).hexdigest(),
              'results':results,'broker_verified':False,'out_of_sample':False,
              'type_a_b_certified':False,'execution_allowed':False,
              'structure_comparison':'WINDOW baseline vs CONTIGUOUS_HISTORY structure; identical last-12 efficiency, ATR, band, thresholds and confirmed pivot windows. No gap bridging. Diagnostic alternative NOT adopted.',
              'warning':'Publisher weekly calendar hypothesis; historical exceptions unverified. Existing experimental regime classifier. Outcomes use assumed spread and fixed stops, omit commissions/slippage/margin. R summaries are independent resolved outcomes, not account returns. UNKNOWN and unresolved candidates are retained, never counted as zero or winners. No model selection or threshold optimization.'}
    (root/'public_xau_h4_alignment.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({**report,'results':{k:{'groups':v['groups'],'regime_reason_counts':v['regime_reason_counts'],
        'full_contiguous_structure_diagnostic':{a:b for a,b in v['full_contiguous_structure_diagnostic'].items() if a!='annotations'}} for k,v in results.items()}}))
    return report

if __name__=='__main__': run()
