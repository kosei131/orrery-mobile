"""Causal confirmation/retest plans -> existing pinned tick/account engines.
First-stage fixed-distance SL/TP anchored to known M5 close, not future fill.
No public M1-to-tick fabrication; broker valuation/fees required explicitly.
"""
import json
from hashlib import sha256
from math import isfinite
from collections import Counter
from orrery_xau_confirmation_entry_comparison import entry_plans
from orrery_xau_h4_alignment import START, END
from lsr03_account_replay import replay_account
from lsr03_tick_study import load_catalog_ticks


def compile_plans(confirmations, observations, m5, *, symbol, fixed_distance,
                  target_r, entry_delay_msc, entry_window_msc, max_holding_msc):
    if symbol not in ('XAUUSD','USDJPY'):
        raise ValueError('Explicit supported symbol required')
    for v in (fixed_distance,target_r):
        if type(v) not in (int,float) or not isfinite(v) or v<=0:
            raise ValueError('Explicit positive reference distance/reward required')
    if (any(type(v) is not int or v<=0 for v in (entry_delay_msc,entry_window_msc,max_holding_msc))
            or entry_delay_msc>=entry_window_msc):
        raise ValueError('Post-close delay and bounded entry window required')
    refs={}
    for b in m5:
        t=b['close_time'];price=b['close']
        if type(t) is not int or t in refs or type(price) not in (int,float) or not isfinite(price) or price<=0:
            raise ValueError('Unique confirmed close references required')
        refs[t]=price
    universe=[c for c in confirmations if START<=c['confirmation_close']<END]
    indexed={}
    for o in observations:
        key=(o['sweep_close'],o['confirmation_close'],o['side'])
        if key in indexed:raise ValueError('Duplicate retest observation')
        indexed[key]=o
    output={}
    for mode in ('CONFIRMATION','RETEST'):
        entries,skips=entry_plans(universe,mode=mode,observations=indexed)
        plans=[]
        for e in entries:
            at=e['first_poi_touch_close'];reference=refs[at]
            sign=1 if e['side']=='BUY' else -1
            stop=reference-sign*fixed_distance
            target=reference+sign*fixed_distance*target_r
            if min(stop,target)<=0:raise ValueError('Nonpositive planned stop/target')
            if at*1000+entry_delay_msc>=min(at*1000+entry_window_msc,END*1000):
                skips.append(dict(candidate_id=e['candidate_id'],reason='DELAY_OUTSIDE_STUDY_WINDOW'))
                continue
            identity=':'.join(map(str,e['candidate_id']))
            plans.append(dict(id=identity,symbol=symbol,side=e['side'],known_at_msc=at*1000,
                eligible_after_msc=at*1000+entry_delay_msc,
                expires_at_msc=min(at*1000+entry_window_msc,END*1000),
                stop=stop,target=target,max_holding_msc=max_holding_msc))
        plans.sort(key=lambda p:(p['known_at_msc'],p['id']))
        output[mode]=dict(plans=plans,no_entry=skips)
    return dict(universe=len(universe),modes=output,
                entry_rule='STRICTLY_POST_CONFIRMED_CLOSE_FIRST_ELIGIBLE_QUOTE',
                target_rule='KNOWN_M5_CLOSE_FIXED_DISTANCE_AND_R_NOT_FILL_ANCHORED_NOT_2_6',
                execution_allowed=False)


def compare_confirmation_accounts(path, *, expected_catalog_sha256, bar_source,
        as_of, confirmations, observations, m5, fixed_distance, target_r,
        entry_delay_msc, entry_window_msc, max_holding_msc,
        volume_min,volume_max,volume_step,pnl_quote,round_trip_cost_per_lot_usd,
        cost_source,slippage,max_ticks=500000,daily_boundary_utc_hour=10,
        carry_quote=None,carry_source=None,boundary_quote_max_age_msc=0):
    loaded=load_catalog_ticks(path,expected_catalog_sha256=expected_catalog_sha256,
        bar_source=bar_source,as_of=as_of,max_ticks=max_ticks)
    if loaded['blocked']:
        return dict(status='BLOCKED_GLOBAL_TICK_QUALITY',accounts=None,audit=loaded['audit'],
                    execution_allowed=False,market_edge_verified=False,six_month_backtest_complete=False)
    compiled=compile_plans(confirmations,observations,m5,symbol=loaded['symbol'],
        fixed_distance=fixed_distance,target_r=target_r,entry_delay_msc=entry_delay_msc,
        entry_window_msc=entry_window_msc,max_holding_msc=max_holding_msc)
    accounts={};omitted={}
    for mode,item in compiled['modes'].items():
        plans=[];missing=[]
        for p in item['plans']:
            if p['known_at_msc']<loaded['start_msc'] or p['eligible_after_msc']>=loaded['end_msc']:
                missing.append(dict(id=p['id'],reason='OUTSIDE_PINNED_QUOTE_HORIZON'))
            else:plans.append(p)
        omitted[mode]=dict(no_entry=item['no_entry'],outside_tick_horizon=missing,
                           submitted_plans=len(plans))
        accounts[mode]=replay_account(loaded['ticks'],plans,symbol=loaded['symbol'],
            volume_min=volume_min,volume_max=volume_max,volume_step=volume_step,
            pnl_quote=pnl_quote,round_trip_cost_per_lot_usd=round_trip_cost_per_lot_usd,
            cost_source=cost_source,slippage=slippage,max_quotes=max_ticks,
            daily_boundary_utc_hour=daily_boundary_utc_hour,carry_quote=carry_quote,
            carry_source=carry_source,boundary_quote_max_age_msc=boundary_quote_max_age_msc)
    return dict(status='CONFIRMATION_RETEST_INDEPENDENT_ACCOUNT_RESEARCH',
        accounts=accounts,universe=compiled['universe'],omitted=omitted,
        compiled_modes=compiled['modes'],
        config=dict(fixed_distance=fixed_distance,target_r=target_r,entry_delay_msc=entry_delay_msc,
            entry_window_msc=entry_window_msc,max_holding_msc=max_holding_msc,
            volume_min=volume_min,volume_max=volume_max,volume_step=volume_step,
            round_trip_cost_per_lot_usd=round_trip_cost_per_lot_usd,cost_source=cost_source,
            slippage=slippage,daily_boundary_utc_hour=daily_boundary_utc_hour,
            carry_source=carry_source,boundary_quote_max_age_msc=boundary_quote_max_age_msc),
        decision_reason_counts={m:dict(Counter(d.get('reason','ENTRY') for d in a['decisions'])) for m,a in accounts.items()},
        entry_rule=compiled['entry_rule'],target_rule=compiled['target_rule'],
        catalog_sha256=expected_catalog_sha256,bar_source=bar_source,
        input_sha256=sha256(json.dumps([confirmations,observations,m5],sort_keys=True,allow_nan=False).encode()).hexdigest(),
        execution_allowed=False,market_edge_verified=False,six_month_backtest_complete=False,
        bar_provenance_verified=False,
        caveat='Two independent $3000 accounts; single symbol and one active position each, same pinned quotes and explicit caller valuation/costs. Reference-close stop/TP differs from earlier next-M1-open fill-anchored hypotheses. No margin, multi-position additions, broker authentication or six-month proof. Open positions retained; timeout uses first actual quote at/after deadline. Three-loss latch does not reset automatically.')
