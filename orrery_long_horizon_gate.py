"""Fail-closed coverage gate for long-horizon ORRERY FX price-reference studies.

Consumes an existing audited TradingView replay report. No orders, optimization,
price reconstruction, profit assertion, or mutation of the report.
"""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from math import isfinite

MIN_DAYS=180
MIN_CANDIDATES=30

def _time(s):
    t=datetime.fromisoformat(s.replace('Z','+00:00'))
    if t.utcoffset()!=timedelta(0):
        raise ValueError('Explicit UTC timestamps required')
    return t

def assess(report, *, train_days=120, min_days=MIN_DAYS, min_candidates=MIN_CANDIDATES):
    if (type(train_days) is not int or type(min_days) is not int or
            type(min_candidates) is not int or train_days<=0 or min_days<=train_days or min_candidates<1):
        raise ValueError('Valid precommitted evaluation gates required')
    if (not isinstance(report,dict) or
            report.get('status')!='EXPLORATORY_WINDOW_RESET_GROSS_REFERENCE_ONLY'
            or report.get('execution_allowed') is not False
            or report.get('actual_profit_usd') is not None
            or report.get('continuous_backtest_complete') is not False):
        raise ValueError('Unpromoted gross reference report required')
    span=report['common_range']
    start=_time(span['start_open_utc'])
    end=_time(span['end_nominal_close_utc'])
    if end<=start:
        raise ValueError('Positive common coverage required')
    split=start+timedelta(days=train_days)
    rows=report['candidates']
    if not isinstance(rows,list) or len(rows)>100000:
        raise ValueError('Bounded candidate rows required')
    seen=set();cohorts={'train':[],'holdout':[],'boundary_excluded':[]}
    for row in rows:
        plan=row['plan'];key=plan['id'];at=plan['known_at_msc']
        if (not isinstance(key,str) or key in seen or type(at) is not int
                or plan.get('symbol')!='XAUUSD'):
            raise ValueError('Unique pinned XAUUSD candidates required')
        seen.add(key)
        when=datetime.fromtimestamp(at/1000,timezone.utc)
        if not start<=when<end:
            raise ValueError('Entry outside covered common range')
        status=row.get('reference_status')
        val=row.get('reference_r')
        if status=='CLOSED_REFERENCE':
            if type(val) not in (int,float) or not isfinite(val):
                raise ValueError('Closed result requires finite gross R')
        elif status in ('CENSORED_AT_WINDOW_END','AMBIGUOUS_INTRABAR'):
            if val is not None:
                raise ValueError('Unresolved results must stay unknown')
        else:
            raise ValueError('Unknown reference resolution')
        exit_ms=row.get('reference_r_exit_at')
        if status=='CLOSED_REFERENCE':
            if type(exit_ms) is not int or exit_ms<at:
                raise ValueError('Valid exit timestamp required')
            exit_at=datetime.fromtimestamp(exit_ms/1000,timezone.utc)
            if exit_at>=end:
                raise ValueError('Exit beyond covered interval')
        else:
            if exit_ms is not None:
                raise ValueError('Unresolved candidate cannot claim an exit timestamp')
            exit_at=None
        if when<split and (exit_at is None or exit_at>=split):
            group='boundary_excluded'
        else:
            group='train' if when<split else 'holdout'
        cohorts[group].append(row)
    def summary(items):
        vals=[r['reference_r'] for r in items if r['reference_status']=='CLOSED_REFERENCE']
        wins=sum(v>0 for v in vals);losses=sum(v<0 for v in vals)
        return dict(candidates=len(items),closed=len(vals),unresolved=len(items)-len(vals),
            gross_mean_closed_r=sum(vals)/len(vals) if vals else None,
            gross_win_rate_closed=wins/len(vals) if vals else None,
            all_resolved=bool(items) and len(vals)==len(items),
            net_expectancy_r=None,profit_factor_net=None,account_max_drawdown=None)
    elapsed_days=(end-start).total_seconds()/86400
    train=summary(cohorts['train']);test=summary(cohorts['holdout'])
    # A six-month first-to-last timestamp is NOT six months of observed history.
    # Require explicitly reported, nonoverlapping coverage windows and account for gaps.
    windows=report.get('windows')
    if not isinstance(windows,list) or not windows:
        raise ValueError('Observed replay windows required')
    coverage_seconds=0.0
    previous_end=None
    train_seconds=holdout_seconds=0.0
    for w in windows:
        a=_time(w['start_open_utc']);b=_time(w['end_close_utc'])
        if not start<=a<b<=end or (previous_end is not None and a<previous_end):
            raise ValueError('Ordered nonoverlapping replay coverage required')
        previous_end=b
        coverage_seconds+=(b-a).total_seconds()
        train_seconds+=max(0.0,(min(b,split)-a).total_seconds())
        holdout_seconds+=max(0.0,(b-max(a,split)).total_seconds())
    observed_days=coverage_seconds/86400
    # Observed-hour thresholds are diagnostic, not a claim that weekend gaps are valid sessions.
    # A 100% calendar-hour requirement would reject normal weekend closures.
    train_span_days=train_days
    holdout_span_days=(end-split).total_seconds()/86400
    train_ratio=(train_seconds/86400)/train_span_days
    holdout_ratio=(holdout_seconds/86400)/holdout_span_days if holdout_span_days>0 else 0
    coverage_ready=(elapsed_days>=min_days and split<end and
                    train_ratio>=0.65 and holdout_ratio>=0.65)

    sample_ready=train['closed']>=min_candidates and test['closed']>=min_candidates
    no_unresolved=train['all_resolved'] and test['all_resolved'] and not cohorts['boundary_excluded']
    return dict(status='LONG_HORIZON_GATED_RESEARCH_ONLY',span_days=elapsed_days,observed_days=observed_days,
        observed_train_days=train_seconds/86400,observed_holdout_days=holdout_seconds/86400,
        train_calendar_coverage_ratio=train_ratio,holdout_calendar_coverage_ratio=holdout_ratio,
        session_calendar_authenticated=False,
        split_utc=split.isoformat(),minimum_days=min_days,minimum_closed_per_partition=min_candidates,
        observed_window_count=len(report.get('windows',[])),coverage_gate_passed=coverage_ready,
        sample_gate_passed=sample_ready,resolution_gate_passed=no_unresolved,
        cohorts=dict(train=train,holdout=test,boundary_excluded=summary(cohorts['boundary_excluded'])),
        gross_price_only=True,bid_ask_costs_verified=False,continuous_session_replay_verified=False,
        six_month_backtest_complete=False,out_of_sample_net_edge_verified=False,
        actual_profit_usd=None,execution_allowed=False,
        next_action='Acquire continuous session-audited M5/M15/H4 and matched broker Bid/Ask/fees; do not optimize on holdout')

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('reference');p.add_argument('--output',required=True)
    args=p.parse_args(argv)
    source=Path(args.reference);output=Path(args.output)
    if source.is_symlink() or not source.is_file() or source.stat().st_size>8*1024*1024:
        raise ValueError('Bounded regular input required')
    if output.resolve()==source.resolve() or output.exists() or output.is_symlink():
        raise ValueError('Exclusive separate output required')
    result=assess(json.loads(source.read_text(encoding='utf-8')))
    with output.open('x',encoding='utf-8') as f:
        json.dump(result,f,ensure_ascii=False,allow_nan=False,indent=2)
    print(result['status'], 'coverage=',result['coverage_gate_passed'])
    return 0
if __name__=='__main__':
    raise SystemExit(main())
