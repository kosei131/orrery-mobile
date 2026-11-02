# SPDX-License-Identifier: GPL-3.0-only
"""Offline prospective cohort gate; temporal eligibility is not proof of edge."""
import argparse
import ast
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from orrery_history_app import PARAMETERS
from orrery_tradingview_bundle_audit import audit_bundle, _utc
from orrery_tradingview_halftrend_study import study

ROOT = Path(__file__).resolve().parent
SCHEMA = 'ORRERY_HALFTREND_PROSPECTIVE_V1'
HALFTREND = dict(amplitude=2, channel_deviation=2, atr_period=100)


def code_pins(root=ROOT):
    """Pin local Python imports recursively, including imports inside functions."""
    pending=['orrery_halftrend_holdout', 'orrery_tradingview_halftrend_study']; pins={}
    while pending:
        name=pending.pop(); path=root/(name+'.py')
        if path.name in pins or not path.is_file():continue
        raw=path.read_bytes(); pins[path.name]=sha256(raw).hexdigest()
        for node in ast.walk(ast.parse(raw)):
            if isinstance(node,ast.Import):pending.extend(x.name.split('.')[0] for x in node.names)
            elif isinstance(node,ast.ImportFrom) and node.module:pending.append(node.module.split('.')[0])
    return dict(sorted(pins.items()))


def decode_plan(raw, expected_sha256):
    if not isinstance(raw,bytes) or len(raw)>1024*1024 or sha256(raw).hexdigest()!=expected_sha256:
        raise ValueError('Frozen plan hash/size mismatch')
    def reject(value):raise ValueError('Non-finite plan')
    p=json.loads(raw,parse_constant=reject)
    if p.get('schema')!=SCHEMA or p.get('parameters')!=PARAMETERS or p.get('halftrend_parameters')!=HALFTREND:
        raise ValueError('Frozen strategy parameters required')
    if p.get('execution_allowed') is not False or p.get('automatic_adoption_allowed') is not False:
        raise ValueError('Research-only plan required')
    frozen=_utc(p['frozen_at_utc']);start=_utc(p['start_open_utc']);end=_utc(p['end_close_utc'])
    if not frozen<start<end or end-start!=28*86400:
        raise ValueError('Prospective fixed 28-day pilot required')
    if p.get('code_sha256')!=code_pins():
        raise ValueError('Research code changed after freeze; do not silently reuse plan')
    if p.get('source_declared')!='OANDA:XAUUSD via TradingView MCP':
        raise ValueError('Fixed source required')
    return p


def evaluate(raw, plan_raw, *, plan_sha256, zip_sha256, now=None):
    p=decode_plan(plan_raw,plan_sha256)
    if sha256(raw).hexdigest()!=zip_sha256:raise ValueError('Input ZIP hash mismatch')
    if zip_sha256==p['discovery_zip_sha256']:raise ValueError('Discovery ZIP is not a new period')
    audit=audit_bundle(raw)
    cutoff=_utc(audit['cutoff_utc'])
    current=(now or datetime.now(timezone.utc))
    if current.utcoffset() is None:raise ValueError('Aware observation time required')
    if cutoff>current.timestamp():raise ValueError('Future data cutoff rejected')
    span=audit['common_range']
    if span['elapsed_seconds']<=0:raise ValueError('No common evaluation interval')
    start=_utc(span['start_open_utc']);end=_utc(span['end_nominal_close_utc'])
    # Require an explicitly sliced common evaluation range. No earlier warmup is
    # passed to the existing study, which already clips every frame to this range.
    if start<_utc(p['start_open_utc']) or end>_utc(p['end_close_utc']):
        raise ValueError('Common evaluation interval is outside frozen pilot')
    result=study(raw,expected_zip_sha256=zip_sha256)
    if result['parameters']!=p['parameters'] or result['halftrend_parameters']!=p['halftrend_parameters']:
        raise ValueError('Runtime strategy differs from frozen plan')
    complete=(start==_utc(p['start_open_utc']) and end==_utc(p['end_close_utc']))
    return dict(status='PROSPECTIVE_TEMPORAL_COHORT_REVIEW_ONLY',plan_sha256=plan_sha256,
        input_zip_sha256=zip_sha256,observed_at_utc=current.astimezone(timezone.utc).isoformat(),
        partial_period=not complete,independent_holdout_verified=False,
        source_authenticity_verified=False,complete_session_coverage_verified=False,
        discovery_summaries=p['discovery_summaries'],prospective_study=result,
        comparison_scope='SAME_FIXED_PARAMETERS_DIFFERENT_OBSERVED_PERIODS_GROSS_ONLY',
        verdict='HOLD_NO_AUTOMATIC_ADOPTION',actual_profit_usd=None,execution_allowed=False,
        net_expectancy_r=None,account_return_pct=None,account_max_dd_usd=None,
        missing=['BROKER_BID_ASK_FEES_CARRY','HISTORICAL_USD_VALUATION',
                 'INDEPENDENT_EXPOSURE_ATTESTATION','SESSION_COMPLETENESS',
                 'REVERSAL04_OBSERVATIONS','LSR01_INDEPENDENT_PATH','UNDEFINED_2_6'])


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('plan','zip','output'):p.add_argument('--'+key,required=True,type=Path)
    p.add_argument('--plan-sha256',required=True);p.add_argument('--zip-sha256',required=True)
    a=p.parse_args(argv)
    with a.plan.open('rb') as f:plan=f.read(1024*1024+1)
    with a.zip.open('rb') as f:raw=f.read(16*1024*1024+1)
    if len(raw)>16*1024*1024:raise ValueError('ZIP budget exceeded')
    r=evaluate(raw,plan,plan_sha256=a.plan_sha256,zip_sha256=a.zip_sha256)
    with a.output.open('x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,allow_nan=False,indent=2);f.write('\n')
    return 0

if __name__=='__main__':raise SystemExit(main())
