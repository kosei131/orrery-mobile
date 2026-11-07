# SPDX-License-Identifier: GPL-3.0-only
"""Disjoint prospective ZIP studies, never a continuous account backtest."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from orrery_halftrend_holdout import decode_plan, evaluate
from orrery_tradingview_bundle_audit import audit_bundle, _utc, _iso
from orrery_tradingview_window_replay import _summary

COHORTS=('HALFTREND_ALIGNED','HALFTREND_OPPOSED','HALFTREND_NOT_READY')


def review(inputs, plan_raw, *, plan_sha256, now=None):
    """Each input has raw ZIP bytes and an externally retained SHA256.

    Refuse overlapping common spans rather than selecting a winning revision.
    Gaps and boundaries reset study state; no prices or unknown costs are filled.
    """
    plan=decode_plan(plan_raw,plan_sha256)
    if not isinstance(inputs,list) or not 1<=len(inputs)<=8:
        raise ValueError('One to eight explicit ZIP inputs required')
    checked=[];pins=set();budget=0
    for item in inputs:
        if not isinstance(item,dict) or set(item)!={'raw','zip_sha256'}:
            raise ValueError('Exact ZIP bytes and pin required')
        raw=item['raw'];pin=item['zip_sha256']
        if not isinstance(raw,bytes) or not 0<len(raw)<=16*1024*1024:
            raise ValueError('ZIP byte budget exceeded')
        budget+=len(raw)
        if budget>32*1024*1024:raise ValueError('Batch byte budget exceeded')
        if sha256(raw).hexdigest()!=pin:raise ValueError('Input ZIP hash mismatch')
        if pin in pins:raise ValueError('Repeated ZIP input')
        pins.add(pin)
        audit=audit_bundle(raw);span=audit['common_range']
        if span['elapsed_seconds']<=0:raise ValueError('No common evaluation interval')
        checked.append((_utc(span['start_open_utc']),_utc(span['end_nominal_close_utc']),item))
    checked.sort(key=lambda row:(row[0],row[1]))
    for left,right in zip(checked,checked[1:]):
        if right[0]<left[1]:raise ValueError('Overlapping evaluation spans; no revision selection allowed')
    current=now or datetime.now(timezone.utc)
    reports=[];rows=[];candidate_ids=set();gaps=[];cursor=_utc(plan['start_open_utc'])
    for start,end,item in checked:
        result=evaluate(item['raw'],plan_raw,plan_sha256=plan_sha256,
                        zip_sha256=item['zip_sha256'],now=current)
        if cursor<start:gaps.append(dict(start_open_utc=_iso(cursor),end_close_utc=_iso(start),elapsed_seconds=start-cursor))
        cursor=end
        study=result['prospective_study']
        for candidate in study['candidates']:
            cid=candidate['plan']['id'];at=candidate['entry_reference_at_s']
            if cid in candidate_ids:raise ValueError('Repeated candidate ID across ZIP studies')
            if not start<at<=end or candidate['halftrend_group'] not in COHORTS:
                raise ValueError('Candidate outside declared segment or cohort')
            candidate_ids.add(cid);rows.append(dict(candidate,batch_zip_sha256=item['zip_sha256']))
        reports.append(result)
    end=_utc(plan['end_close_utc'])
    if cursor<end:gaps.append(dict(start_open_utc=_iso(cursor),end_close_utc=_iso(end),elapsed_seconds=end-cursor))
    rows.sort(key=lambda row:(row['entry_reference_at_s'],row['plan']['id']))
    groups=dict(LSR02=rows,VHF03=[r for r in rows if r['vhf_group']=='VHF_PASS'])
    groups.update({g:[r for r in rows if r['halftrend_group']==g] for g in COHORTS})
    return dict(status='DISJOINT_ZIP_COHORT_REVIEW_ONLY',plan_sha256=plan_sha256,
        batch_code_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        observed_at_utc=current.astimezone(timezone.utc).isoformat(),
        sorted_zip_sha256=[r['input_zip_sha256'] for r in reports],reports=reports,
        discovery_summaries=plan['discovery_summaries'],summaries={g:_summary(v) for g,v in groups.items()},
        candidates=rows,unsubmitted_common_span_gaps=gaps,
        submitted_common_span_seconds=sum(end-start for start,end,_ in checked),
        planned_period_seconds=end-_utc(plan['start_open_utc']),
        partial_period=bool(gaps),complete_session_coverage_verified=False,
        boundary_state_reset=True,continuous_strategy_equivalence_verified=False,
        summary_scope='UNION_OF_DISJOINT_INDEPENDENT_RESET_WINDOWS_GROSS_ONLY',
        independent_holdout_verified=False,halftrend_filter_adopted=False,reversal04_compared=False,
        six_month_backtest_complete=False,account_risk_controls_applied=False,
        net_expectancy_r=None,account_return_pct=None,account_max_dd_usd=None,actual_profit_usd=None,
        verdict='HOLD_NO_AUTOMATIC_ADOPTION',execution_allowed=False)


def _read(path,limit):
    with Path(path).open('rb') as f:raw=f.read(limit+1)
    if len(raw)>limit:raise ValueError('File byte budget exceeded')
    return raw


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('manifest','plan','output'):p.add_argument('--'+key,required=True,type=Path)
    for key in ('manifest-sha256','plan-sha256'):p.add_argument('--'+key,required=True)
    a=p.parse_args(argv);raw=_read(a.manifest,1024*1024)
    if sha256(raw).hexdigest()!=a.manifest_sha256:raise ValueError('Manifest hash mismatch')
    manifest=json.loads(raw)
    if not isinstance(manifest,list) or not 1<=len(manifest)<=8:raise ValueError('Bounded ZIP manifest required')
    inputs=[]
    for item in manifest:
        if not isinstance(item,dict) or set(item)!={'zip_path','zip_sha256'}:raise ValueError('Exact manifest fields required')
        inputs.append(dict(raw=_read(item['zip_path'],16*1024*1024),zip_sha256=item['zip_sha256']))
    result=review(inputs,_read(a.plan,1024*1024),plan_sha256=a.plan_sha256)
    result['manifest_sha256']=a.manifest_sha256
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,allow_nan=False,indent=2);f.write('\n')
    return 0

if __name__=='__main__':raise SystemExit(main())
