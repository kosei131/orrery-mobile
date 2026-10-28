"""Existing LSR02/03 traces -> as-of plans -> two independent $3000 accounts.

Pinned quote loader and account engine are reused. This intraday single-symbol
benchmark does not establish broker costs, six-month returns or real orders.
"""
from hashlib import sha256
import json
from math import isfinite
from lsr03_adapter import compare_vhf, collect_retests
from lsr03_tick_study import load_catalog_ticks
from lsr03_account_replay import replay_account


def _clock(seconds):
    value=seconds*1000
    if type(value) not in (int,float) or not isfinite(value) or value!=int(value):
        raise ValueError('Exact millisecond candidate clock required')
    return int(value)


def build_account_plans(symbol,h4,m15,m5,*,as_of,buffer,target_r,
                        period=14,min_vhf=.4,left=1,right=1,lifetime=6000,
                        entry_delay_msc=1,max_candidates=1000):
    if type(target_r) not in (int,float) or not isfinite(target_r) or target_r<=0:
        raise ValueError('Explicit positive benchmark target R required')
    if type(entry_delay_msc) is not int or entry_delay_msc<1:
        raise ValueError('Post-confirmation delay required')
    compared=compare_vhf(symbol,h4,m15,m5,as_of=as_of,buffer=buffer,period=period,
                         min_vhf=min_vhf,left=left,right=right,lifetime=lifetime)
    candidates=collect_retests(compared,symbol,max_candidates=max_candidates)
    bars={b['close_time']:b for b in m5}
    plans=[];cancellations=[];groups={};omitted=[]
    for c in candidates:
        if c['retest_at'] not in bars:raise ValueError('Missing confirmed RETEST candle')
        reference=bars[c['retest_at']]['close'];stop=c['stop']
        sign=1 if c['side']=='BUY' else -1
        distance=sign*(reference-stop);target=reference+sign*distance*target_r
        at=_clock(c['retest_at']);eligible=at+entry_delay_msc
        expiry=_clock(c['sweep_at']+lifetime)
        if not all(isfinite(v) and v>0 for v in (reference,stop,target,distance)) or eligible>=expiry:
            omitted.append(dict(id=c['id'],reason='INVALID_GEOMETRY_OR_EXPIRED_RETEST'));continue
        plans.append(dict(id=c['id'],symbol=symbol,side=c['side'],known_at_msc=at,
            eligible_after_msc=eligible,expires_at_msc=expiry,stop=stop,target=target))
        groups[c['id']]=c['group']
        if c['invalid_at'] is not None:
            cancellations.append(dict(id=c['id'],known_at_msc=_clock(c['invalid_at'])))
    cancellations.sort(key=lambda e:(e['known_at_msc'],e['id']))
    return dict(plans=plans,cancellations=cancellations,groups=groups,omitted=omitted,
        target_rule='RETEST_CLOSE_FIXED_R_BENCHMARK_NOT_2_6',
        entry_rule='FIRST_QUOTE_AFTER_CONFIRMED_RETEST_PLUS_DELAY',execution_allowed=False)


def compare_catalog_accounts(path,*,expected_catalog_sha256,h4,m15,m5,bar_source,
                             as_of,buffer,target_r,volume_min,volume_max,volume_step,
                             pnl_quote,round_trip_cost_per_lot_usd,cost_source,slippage,
                             period=14,min_vhf=.4,left=1,right=1,lifetime=6000,
                             entry_delay_msc=1,max_ticks=500000,max_candidates=1000,
                             daily_boundary_utc_hour=10,carry_quote=None,carry_source=None,
                             boundary_quote_max_age_msc=0):
    loaded=load_catalog_ticks(path,expected_catalog_sha256=expected_catalog_sha256,
                              bar_source=bar_source,as_of=as_of,max_ticks=max_ticks)
    if loaded['blocked']:
        return dict(status='BLOCKED_GLOBAL_TICK_QUALITY',audit=loaded['audit'],accounts=None,
                    execution_allowed=False,market_edge_verified=False,six_month_backtest_complete=False)
    compiled=build_account_plans(loaded['symbol'],h4,m15,m5,as_of=as_of,buffer=buffer,
        target_r=target_r,period=period,min_vhf=min_vhf,left=left,right=right,lifetime=lifetime,
        entry_delay_msc=entry_delay_msc,max_candidates=max_candidates)
    plans=[];omitted=list(compiled['omitted'])
    for plan in compiled['plans']:
        if plan['known_at_msc']<loaded['start_msc']:
            omitted.append(dict(id=plan['id'],reason='RETEST_BEFORE_PINNED_TICK_COVERAGE'))
        else:plans.append(plan)
    selected=[p for p in plans if compiled['groups'][p['id']]=='VHF_PASS']
    visible_ids={p['id'] for p in plans}
    visible_cancellations=[e for e in compiled['cancellations'] if e['id'] in visible_ids]
    accounts={}
    for label,subset in (('LSR02',plans),('LSR03',selected)):
        ids={p['id'] for p in subset}
        cancellations=[e for e in compiled['cancellations'] if e['id'] in ids]
        accounts[label]=replay_account(loaded['ticks'],subset,symbol=loaded['symbol'],
            volume_min=volume_min,volume_max=volume_max,volume_step=volume_step,
            pnl_quote=pnl_quote,round_trip_cost_per_lot_usd=round_trip_cost_per_lot_usd,
            cost_source=cost_source,slippage=slippage,initial_equity=3000,
            daily_boundary_utc_hour=daily_boundary_utc_hour,max_quotes=max_ticks,
            cancellations=cancellations,carry_quote=carry_quote,carry_source=carry_source,
            boundary_quote_max_age_msc=boundary_quote_max_age_msc)
    return dict(status='MATCHED_INTRADAY_ACCOUNT_RESEARCH' if carry_quote is None else 'MATCHED_SINGLE_SYMBOL_CARRY_ACCOUNT_RESEARCH',symbol=loaded['symbol'],
        accounts=accounts,candidate_counts=dict(LSR02=len(plans),LSR03=len(selected),
            VHF_FILTERED=len(plans)-len(selected)),plans=plans,
        vhf_groups={key:value for key,value in compiled['groups'].items() if key in visible_ids},
        cancellations=visible_cancellations,omitted=omitted,
        target_rule=compiled['target_rule'],entry_rule=compiled['entry_rule'],
        comparison_basis='INDEPENDENT_3000_USD_ACCOUNTS_SAME_QUOTES_AND_ASSUMPTIONS',
        catalog_sha256=expected_catalog_sha256,
        bar_input_sha256=sha256(json.dumps([h4,m15,m5],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),
        config=dict(buffer=buffer,target_r=target_r,period=period,min_vhf=min_vhf,left=left,
            right=right,lifetime=lifetime,entry_delay_msc=entry_delay_msc,
            volume_min=volume_min,volume_max=volume_max,volume_step=volume_step,
            round_trip_cost_per_lot_usd=round_trip_cost_per_lot_usd,cost_source=cost_source,
            slippage=slippage,daily_boundary_utc_hour=daily_boundary_utc_hour,
            carry_source=carry_source,carry_enabled=carry_quote is not None,
            boundary_quote_max_age_msc=boundary_quote_max_age_msc),
        global_tick_audit=loaded['audit'],bar_provenance_verified=False,
        execution_allowed=False,market_edge_verified=False,six_month_backtest_complete=False,
        caveat='Single symbol/one position per account. Caller historical USD valuation, fees and optional carry unverified. Accounts may take different trades due to their own capital/stops. Carry requires explicit as-of boundary data; future carry not reserved in sizing. No margin/combined-symbol or six-month real-market return claim.')
