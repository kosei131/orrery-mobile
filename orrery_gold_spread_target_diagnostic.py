# SPDX-License-Identifier: GPL-3.0-only
"""Descriptive Gold spread-to-target diagnostics from a pinned public audit.

No assumptions about actual entry, exit fills or profitability. Historical
quotes are tick weighted, not a broker cost model. No strategy adoption.
"""
import argparse
import json
from hashlib import sha256
from math import isfinite
from pathlib import Path

TARGET_R=(0.05,0.10,0.25,1.5)
STOP_PRICE_DISTANCE=6.0
PINNED_ZIP_SHA256='feb3b05031db23ec7c9eea706cd050e32656b5771ba01fe734c39ce2a95285e1'


def summarize(audit, *, fixed_stop_price=STOP_PRICE_DISTANCE, target_rs=TARGET_R):
    if not isinstance(audit,dict) or audit.get('status')!='GOLD_CHUNKED_DIAGNOSTIC_NO_BAR_EXPORT':
        raise ValueError('Expected original Gold diagnostic evidence')
    if audit.get('symbol')!='XAUUSD' or audit.get('source_month_fixed_est')!='202610':
        raise ValueError('Exact 2026-10 Gold source only')
    if audit.get('original_zip_sha256')!=PINNED_ZIP_SHA256:
        raise ValueError('Gold ZIP pin mismatch')
    if audit.get('chronological_bar_exported') is not False or audit.get('strategy_replay_allowed') is not False:
        raise ValueError('Diagnostic data may not claim verified chronology')
    if not isinstance(fixed_stop_price,(int,float)) or not isfinite(fixed_stop_price) or fixed_stop_price<=0:
        raise ValueError('Positive explicit reference stop distance required')
    if not isinstance(target_rs,(tuple,list)) or len(target_rs)>10 or not target_rs:
        raise ValueError('Bounded target list required')
    for r in target_rs:
        if type(r) not in (int,float) or not isfinite(r) or r<=0:
            raise ValueError('Positive finite reference target R required')
    by_hour=audit.get('spread_by_declared_utc_hour')
    summary=audit.get('synchronous_tick_spread_price')
    ticks=audit.get('ticks')
    if not isinstance(by_hour,dict) or set(by_hour)!={str(i) for i in range(24)} or type(ticks) is not int or ticks<=0:
        raise ValueError('Complete hour-by-hour spread evidence required')
    if not isinstance(summary,dict) or not all(type(summary.get(k)) in (int,float) and isfinite(summary[k]) and summary[k]>=0 for k in ('median','p95')):
        raise ValueError('Spread median and p95 required')
    hours=[]
    for h in range(24):
        data=by_hour[str(h)]
        if (type(data.get('ticks')) is not int or data['ticks']<=0
            or any(type(data.get(k)) not in (int,float) or not isfinite(data[k]) or data[k]<0 for k in ('median','p95'))
            or data['p95']<data['median']):
            raise ValueError('Invalid hourly spread evidence')
        hours.append(dict(utc_hour=h,quotes=data['ticks'],median=data['median'],p95=data['p95']))
    if sum(h['quotes'] for h in hours)!=ticks:
        raise ValueError('Hourly quote counts do not reconcile')
    comparisons=[]
    for r in target_rs:
        target=fixed_stop_price*r
        # These flags compare historical quote spread to a nominal reference
        # target; they are not executable hours or opportunity probabilities.
        median_hours=[h['utc_hour'] for h in hours if h['median']>=target]
        p95_hours=[h['utc_hour'] for h in hours if h['p95']>=target]
        comparisons.append(dict(target_r=r,gross_target_price_distance=target,
            hourly_median_at_or_above_target=median_hours,
            hourly_p95_at_or_above_target=p95_hours,
            hourly_p95_below_target=[h['utc_hour'] for h in hours if h['p95']<target],
            quote_weighted_hour_coverage_not_trade_coverage=True,
            all_ticks_median_spread_to_target=summary['median']/target,
            all_ticks_p95_spread_to_target=summary['p95']/target,
            utc_hours_where_p95_spread_exceeds_gross_target=p95_hours))
    return dict(status='HISTORICAL_SPREAD_TARGET_SIZE_DIAGNOSTIC_ONLY',
        symbol='XAUUSD',source_month_fixed_est='202610',source_zip_sha256=PINNED_ZIP_SHA256,
        source_ticks=ticks,spread_price_units='XAUUSD quoted price difference',
        reference_stop_price_distance=fixed_stop_price,
        targets=comparisons,hours=hours,
        source_tick_weighted=True,entry_timing_conditioned=False,
        future_costs_verified=False,execution_chronology_verified=False,
        spread_not_additive_if_already_in_bid_ask_fills=True,
        risk_adjusted_performance_verified=False,
        actual_win_rate_pct=None,net_expectancy_r=None,actual_profit_usd=None,
        execution_allowed=False)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit',required=True,type=Path)
    p.add_argument('--audit-sha256',required=True)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args(argv)
    if args.output.exists() or args.output.is_symlink():
        p.error('New output required')
    raw=args.audit.read_bytes()
    if sha256(raw).hexdigest()!=args.audit_sha256:
        raise ValueError('Audit JSON hash mismatch')
    result=summarize(json.loads(raw))
    with args.output.open('x',encoding='utf-8') as out:
        json.dump(result,out,indent=2,allow_nan=False)
    print(json.dumps(dict(source_ticks=result['source_ticks'],targets=result['targets'])))

if __name__=='__main__':
    main()
