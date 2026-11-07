# SPDX-License-Identifier: GPL-3.0-only
"""Pinned TradingView LSR candidates vs causal HalfTrend state; gross R only.

No new trade generation, altered exits, fees assumed zero, or Reversal proxy.
"""
import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import zipfile
from orrery_tradingview_window_replay import replay_bundle,_aligned_windows,_summary
from orrery_tradingview_bundle_audit import _bars,_utc,FRAMES
from orrery_history_app import PARAMETERS
from lsr05_halftrend import calculate,SOURCE_SHA256


def annotate(candidates,indicator_rows):
    """Classify only the row at the exact confirmed entry clock, never later."""
    index={r['at']:r for r in indicator_rows}
    if len(index)!=len(indicator_rows):raise ValueError('Unique HalfTrend clocks required')
    result=[]
    for candidate in candidates:
        at=candidate['entry_reference_at_s'];side=candidate['plan']['side']
        row=index.get(at)
        state=row['state'] if row and row['ready'] else None
        cohort=('HALFTREND_NOT_READY' if state is None else 'HALFTREND_ALIGNED'
                if state==('UP' if side=='BUY' else 'DOWN') else 'HALFTREND_OPPOSED')
        result.append(dict(candidate,halftrend_group=cohort,
            halftrend_at_s=at if row else None,halftrend_ready=bool(row and row['ready']),
            halftrend_state=state,halftrend_line=row['line'] if row and row['ready'] else None,
            reversal04_status='NOT_EVALUATED_EXTERNAL_OBSERVATIONS_NOT_SUPPLIED'))
    return result


def study(raw,*,expected_zip_sha256):
    if (not isinstance(expected_zip_sha256,str) or len(expected_zip_sha256)!=64
            or sha256(raw).hexdigest()!=expected_zip_sha256):
        raise ValueError('Retained TradingView ZIP pin required')
    base=replay_bundle(raw,dict(PARAMETERS));audit=base['bundle_audit']
    start=_utc(audit['common_range']['start_open_utc']);end=_utc(audit['common_range']['end_nominal_close_utc'])
    frames={}
    with zipfile.ZipFile(BytesIO(raw)) as z:
        for name,step in FRAMES.items():
            rows,_=_bars(z.read(name+'.csv'),step,_utc(audit['cutoff_utc']))
            frames[name]=[dict(close_time=r['at']+step,
                **{k:float(r[k]) for k in ('open','high','low','close')})
                for r in rows if start<=r['at'] and r['at']+step<=end]
    windows=list(_aligned_windows(frames));rows=[]
    for i,w in enumerate(windows):
        local=calculate(w['m5'],as_of=w['end_s'],interval=300,amplitude=2,
                        channel_deviation=2,enabled=True)
        rows.extend(annotate([r for r in base['candidates'] if r['window']==i],local['rows']))
    if len(rows)!=len(base['candidates']):raise ValueError('Candidate window reconciliation failed')
    groups={g:[r for r in rows if r['halftrend_group']==g] for g in
        ('HALFTREND_ALIGNED','HALFTREND_OPPOSED','HALFTREND_NOT_READY')}
    root=Path(__file__).resolve().parent
    names=('orrery_tradingview_halftrend_study.py','lsr05_halftrend.py',
           'lsr05_session_clock.py','orrery_history_app.py')
    return dict(status='HALFTREND_STATE_COHORT_GROSS_REFERENCE_ONLY',zip_sha256=expected_zip_sha256,
        common_range=base['common_range'],parameters=dict(PARAMETERS),
        halftrend_parameters=dict(amplitude=2,channel_deviation=2,atr_period=100),
        parameter_sets_tried=1,hypothesis='READY_M5_HALFTREND_STATE_MATCHES_LSR_RETEST_SIDE',
        windows=len(windows),candidates=rows,summaries=dict(LSR02=_summary(rows),
            VHF03=_summary([r for r in rows if r['vhf_group']=='VHF_PASS']),
            **{name:_summary(group) for name,group in groups.items()}),
        halftrend_source_sha256=SOURCE_SHA256,code_sha256=dict(base['code_sha256'],
            **{n:sha256((root/n).read_bytes()).hexdigest() for n in names}),
        original_candidates_and_exits_preserved=True,reset_indicators_at_each_window=True,
        independent_holdout=False,tradingview_indicator_parity_verified=False,
        halftrend_cohort_compared=True,halftrend_filter_adopted=False,reversal04_compared=False,
        excluded_modules=['LSR01_INDEPENDENT_PATH','REVERSAL04','UNDEFINED_2_6'],
        bid_ask_costs_verified=False,account_risk_controls_applied=False,
        actual_profit_usd=None,execution_allowed=False)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--zip',required=True,type=Path);p.add_argument('--zip-sha256',required=True)
    p.add_argument('--output',required=True,type=Path);a=p.parse_args(argv)
    with a.zip.open('rb') as f:raw=f.read(16*1024*1024+1)
    if len(raw)>16*1024*1024:raise ValueError('ZIP budget exceeded')
    report=study(raw,expected_zip_sha256=a.zip_sha256)
    with a.output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(report['summaries'],allow_nan=False));return 0

if __name__=='__main__':raise SystemExit(main())
