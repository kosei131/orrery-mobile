"""Offline paired H4-clock research; unverified weekly partial bars, never orders.

One fixed parameter set, no pre-publication warmup, no gap bridging. Both H4
variants receive exactly the same M5/M15 inputs. Results remain gross references.
"""
import argparse
from hashlib import sha256
import json
from math import ceil, isfinite
from pathlib import Path

from orrery_history_app import (PARAMETERS, STEPS, frames, crosscheck, compare,
                                coverage, session_review)
from orrery_tradingview_window_replay import _aligned_windows
from orrery_real_bars_lsr_bridge import load


def _pin(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()



def diagnose_windows(windows):
    """Count the existing engine's actual decisions; no replacement rule model."""
    from collections import Counter
    from lsr02_replay import replay
    totals=dict(m5_closes=0,m15_sweep_events=0)
    groups={k:Counter() for k in ('h4_states','sweep_dispositions',
                                 'candidate_transitions','invalidation_reasons','invalidation_from_states',
        'h4_context_reasons','h4_context_bars','h4_reason_by_bars','h4_sweep_context_reasons')}
    rows=[]
    for w in windows:
        d={}
        replay('XAUUSD',w['h4'],w['m15'],w['m5'],as_of=w['end_s'],
            buffer=PARAMETERS['buffer'],lifetime=PARAMETERS['lifetime'],
            left=PARAMETERS['left'],right=PARAMETERS['right'],diagnostics=d)
        if (sum(d['h4_states'].values())!=d['m5_closes'] or
                sum(d['sweep_dispositions'].values())!=d['m15_sweep_events'] or
                sum(d['h4_context_reasons'].values())!=d['m5_closes'] or
                sum(d['h4_context_bars'].values())!=d['m5_closes'] or
                sum(d['h4_reason_by_bars'].values())!=d['m5_closes'] or
                sum(d['h4_sweep_context_reasons'].values())!=d['m15_sweep_events']):
            raise ValueError('Replay diagnostic counters do not reconcile')
        for k in totals:totals[k]+=d[k]
        for k in groups:groups[k].update(d[k])
        rows.append(dict(start_s=w['start_s'],end_s=w['end_s'],**d))
    return dict(status='EXISTING_REPLAY_DECISION_COUNTS_ONLY',**totals,
        **{k:dict(v) for k,v in groups.items()},windows=rows,
        repeated_active_state_rows_counted=False,
        m15_scope='SWEEP_EVENTS_AT_OBSERVED_M5_CLOSE_ONLY',
        h4_reason_basis='EXISTING_CONFIRMED_PIVOTS_TWO_HIGHS_AND_TWO_LOWS',
        history_shortage_cause_verified=False,
        candidate_invalidations_are_trade_outcomes=False,
        counts_are_profitability_evidence=False,execution_allowed=False)

def paired_compare(data, session_h4, *, published_at):
    if type(published_at) not in (int,float) or not isfinite(published_at) or published_at<0:
        raise ValueError('Explicit finite schedule publication clock required')
    if set(data)!=set(STEPS):raise ValueError('Three explicit baseline frames required')
    for label, rows in list(data.items())+[('4H',session_h4)]:
        step=STEPS[label]
        if not isinstance(rows,list) or not 1<=len(rows)<=200000:
            raise ValueError('Bounded nonempty frames required')
        previous=None
        for b in rows:
            if (any(type(b.get(k)) not in (int,float) or not isfinite(b[k])
                    for k in ('close_time','open','high','low','close'))
                    or b['close_time']%step or b['close_time']<0
                    or previous is not None and b['close_time']<=previous
                    or not 0<b['low']<=min(b['open'],b['close'])<=max(b['open'],b['close'])<=b['high']):
                raise ValueError('Ordered finite UTC-grid OHLC required')
            previous=b['close_time']
    start=ceil(published_at/14400)*14400
    end=min(rows[-1]['close_time'] for rows in list(data.values())+[session_h4])
    if start>=end:raise ValueError('No post-publication common horizon')
    clipped={k:[dict(b) for b in rows if start<=b['close_time']-STEPS[k] and b['close_time']<=end]
             for k,rows in data.items()}
    session=[dict(b) for b in session_h4 if start<=b['close_time']-14400 and b['close_time']<=end]
    if not all(clipped.values()) or not session:
        raise ValueError('No complete post-publication bars in every frame')
    arms={}
    for name,h4 in (('UTC_COMPLETE_ONLY',clipped['4H']),('WEEKLY_PARTIAL_UNVERIFIED',session)):
        selected=dict(clipped,**{'4H':h4})
        result=compare(selected)
        windows=list(_aligned_windows({'5m':selected['5m'],'15m':selected['15m'],'4h':h4}))
        result.update(decision_diagnostics=diagnose_windows(windows),frame_coverage=coverage(selected),
            common_lower_frames_sha256=_pin([selected['5m'],selected['15m']]),
            replayed_m5_bars=sum(len(w['m5']) for w in windows),
            h4_input_sha256=_pin(h4))
        arms[name]=result
    from datetime import datetime,timezone
    return dict(status='PAIRED_H4_SESSION_GROSS_REFERENCE_RESEARCH_ONLY',
        start_open_utc=datetime.fromtimestamp(start,timezone.utc).isoformat(),
        end_close_utc=datetime.fromtimestamp(end,timezone.utc).isoformat(),
        publication_at_s=published_at,start_open_s=start,end_close_s=end,
        arms=arms,parameters=dict(PARAMETERS),parameter_sets_tried=1,
        h4_variants=2,vhf_thresholds_tried=1,independent_holdout=False,
        warmup_before_start_used=False,source_authenticated=False,
        historical_calendar_verified=False,partial_h4_equivalent_to_full=False,
        candidate_state_carried_across_gaps=False,account_risk_controls_applied=False,
        excluded_modules=['LSR01_INDEPENDENT_PATH','REVERSAL04','HALFTREND05','UNDEFINED_2_6'],
        bid_ask_costs_verified=False,actual_profit_usd=None,
        strategy_adopted=False,execution_allowed=False)


def run(source, bars, output_dir, *, expected_source_sha256):
    source=Path(source); bars=Path(bars); output_dir=Path(output_dir)
    if (not isinstance(expected_source_sha256,str) or len(expected_source_sha256)!=64
            or any(c not in '0123456789abcdef' for c in expected_source_sha256)):
        raise ValueError('Retained original source SHA256 required')
    if (source.is_symlink() or not source.is_file() or source.stat().st_size>100_000_000
            or sha256(source.read_bytes()).hexdigest()!=expected_source_sha256):
        raise ValueError('Original source pin mismatch')
    data=frames(bars)
    baseline_crosscheck=crosscheck(source,data)
    output_dir.mkdir(parents=False,exist_ok=False)
    review=session_review(source,bars,output_dir/'session_diagnostic')
    if (review['original_source_sha256']!=expected_source_sha256
            or review['h4_aggregation'] is None or review['quotes_during_published_closure']):
        raise ValueError('Session source or weekly-clock conflict blocks paired study')
    path=output_dir/'session_diagnostic'/'H4_WEEKLY_SCHEDULE_UNVERIFIED.csv'
    if sha256(path.read_bytes()).hexdigest()!=review['h4_file_sha256']:
        raise ValueError('Session H4 changed')
    from datetime import datetime
    published=datetime.fromisoformat(review['published_report_utc']).timestamp()
    report=paired_compare(data,load(path,'H4')['bars'],published_at=published)
    root=Path(__file__).resolve().parent
    modules=('orrery_history_session_study.py','orrery_history_app.py','orrery_xau_session_coverage.py',
        'orrery_m1_complete_bars.py','orrery_tradingview_window_replay.py','lsr03_account_study.py',
        'lsr03_adapter.py','lsr02_replay.py','lsr02_structure.py','lsr02_sequence.py',
        'lsr03_vhf.py','lsr02_exits.py','lsr02.py','lsr02_regime.py','lsr03_learning_rollup.py')
    report.update(source_sha256=expected_source_sha256,
        baseline_aggregation_crosscheck=baseline_crosscheck,
        session_review=review,code_sha256={n:sha256((root/n).read_bytes()).hexdigest() for n in modules})
    with (output_dir/'comparison.json').open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n')
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True,type=Path);p.add_argument('--bars',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path);p.add_argument('--source-sha256',required=True)
    a=p.parse_args(argv)
    r=run(a.source,a.bars,a.output_dir,expected_source_sha256=a.source_sha256)
    print(json.dumps({k:v['summaries'] for k,v in r['arms'].items()},allow_nan=False))
    return 0

if __name__=='__main__':raise SystemExit(main())
