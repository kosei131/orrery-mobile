"""Versioned research decisions and append-only paired-direction reviews.

Reuses level observer snapshots and Bid/Ask replay. No fitting, live orders,
automatic strategy promotion or causal explanation is implemented.
"""
from hashlib import sha256
from math import isfinite
from pathlib import Path
from lsr04_tick_archive import _encode, _decode, _pin, _read_metadata, _write_exclusive
from lsr04_tick_fills import replay_exit


def _number(value, *, positive=False):
    if type(value) not in (int,float) or not isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError('Explicit finite nonnegative value required')
    return value


def _label(value):
    if not isinstance(value,str) or not value.strip() or len(value)>200 or any(ord(c)<32 for c in value):
        raise ValueError('Bounded nonsecret source/version label required')
    return value


def start_case(path, *, candidate_id, symbol, strategy_version, decision_at_msc,
               entry_after_msc, reference_price, side, original_plan, opposite_plan,
               level_observation, level_tolerance, market_regime,
               entry_thesis, round_trip_cost_per_unit, slippage, cost_source, data_source):
    if symbol not in ('XAUUSD','USDJPY') or side not in ('BUY','SELL'):
        raise ValueError('Canonical symbol and side required')
    for value in (decision_at_msc,entry_after_msc):
        if type(value) is not int or value<0: raise ValueError('UTC integer milliseconds required')
    if entry_after_msc<=decision_at_msc: raise ValueError('Entry strictly after decision required')
    _number(reference_price,positive=True); _number(level_tolerance,positive=True)
    if round_trip_cost_per_unit is not None: _number(round_trip_cost_per_unit,positive=True)
    _number(slippage)
    if market_regime not in ('TREND','RANGE','UNCLEAR','VOLATILE','UNKNOWN'):
        raise ValueError('Explicit market regime required')
    inverse = 'SELL' if side=='BUY' else 'BUY'
    plans = {}
    for name,direction,plan in (('original',side,original_plan),('opposite',inverse,opposite_plan)):
        if not isinstance(plan,dict) or set(plan)!={'stop','target'}:
            raise ValueError('Both direction plans must be fixed before outcome')
        stop,target=(_number(plan[k],positive=True) for k in ('stop','target'))
        if not (stop<reference_price<target if direction=='BUY' else target<reference_price<stop):
            raise ValueError('Invalid predeclared price geometry')
        plans[name]=dict(side=direction,stop=stop,target=target)
    obs = level_observation
    if (not isinstance(obs,dict) or obs.get('execution_allowed') is not False
            or not isinstance(obs.get('levels'),list) or len(obs['levels'])>100):
        raise ValueError('Existing read-only level observer snapshot required')
    observed = _number(obs.get('observed_at'))*1000
    if observed>decision_at_msc: raise ValueError('Future level observation')
    levels=[]
    for level in obs['levels']:
        if not isinstance(level,dict): raise ValueError('Invalid level')
        price = _number(level.get('price'),positive=True)
        known = _number(level.get('confirmed_at'))*1000
        if known>observed: raise ValueError('Level not yet confirmed at observation')
        levels.append(dict(kind=_label(level.get('kind')),price=price,confirmed_at_msc=known,
                           distance_from_reference=abs(price-reference_price),
                           near_reference=abs(price-reference_price)<=level_tolerance))
    context=dict(schema_version=1,candidate_id=_label(candidate_id),symbol=symbol,
        strategy_version=_label(strategy_version),decision_at_msc=decision_at_msc,
        entry_after_msc=entry_after_msc,reference_price=reference_price,plans=plans,
        level_observed_at_msc=observed,levels=levels,level_tolerance=level_tolerance,
        market_regime=market_regime,round_trip_cost_per_unit=round_trip_cost_per_unit,
        entry_thesis=_label(entry_thesis),
        slippage=slippage,cost_source=_label(cost_source),data_source=_label(data_source),
        execution_allowed=False)
    data = _encode(context); root=Path(path); root.mkdir()
    _write_exclusive(root/'decision.json',data)
    return dict(status='RESEARCH_DECISION_SAVED',decision_sha256=sha256(data).hexdigest(),
                execution_allowed=False)


def review_case(path, *, expected_decision_sha256, ticks, as_of_msc):
    _pin(expected_decision_sha256)
    root=Path(path)
    if root.is_symlink() or not root.is_dir(): raise ValueError('Regular case directory required')
    data=_read_metadata(root/'decision.json')
    if sha256(data).hexdigest()!=expected_decision_sha256: raise ValueError('Decision pin mismatch')
    context=_decode(data)
    if (type(context.get('schema_version')) is not int or context['schema_version']!=1
            or context.get('execution_allowed') is not False
            or type(as_of_msc) is not int or as_of_msc<context['entry_after_msc']):
        raise ValueError('Unsupported decision or review time')
    if not isinstance(ticks,list) or not 1<=len(ticks)<=300000:
        raise ValueError('Bounded explicit quotes required')
    prior=None
    for tick in ticks:
        if not isinstance(tick,dict): raise ValueError('Quote record required')
        at=tick.get('time_msc'); bid=tick.get('bid'); ask=tick.get('ask')
        if (type(at) is not int or at<0 or at>as_of_msc or (prior is not None and at<prior)
                or not 0<_number(bid,positive=True)<=_number(ask,positive=True)):
            raise ValueError('Invalid, future or unordered quote')
        prior=at
    results={}
    for name,plan in context['plans'].items():
        result=replay_exit(ticks,side=plan['side'],entry_after_msc=context['entry_after_msc'],
            stop_price=plan['stop'],target_price=plan['target'],slippage=context['slippage'])
        if result['status']=='CLOSED':
            gross=result['price_pnl_per_unit']; cost=context['round_trip_cost_per_unit']
            net=None if cost is None else gross-cost
            if net is not None and not isfinite(net): raise ValueError('Outcome overflow')
            result=dict(result,gross_price_pnl_per_unit=gross,cost_per_unit=cost,
                        net_price_pnl_per_unit=net,result=('UNKNOWN' if net is None else
                            'WIN' if net>0 else 'LOSS' if net<0 else 'BREAKEVEN'))
        else: result=dict(result,result='UNKNOWN',net_price_pnl_per_unit=None)
        if 'entry_at' in result:
            finish=result.get('exit_at',as_of_msc)
            marks=[((q['bid']-result['entry_price']) if plan['side']=='BUY'
                    else (result['entry_price']-q['ask']))
                   for q in ticks if result['entry_at']<=q['time_msc']<=finish]
            result.update(max_favorable_price_per_unit=max([0.,*marks]),
                          max_adverse_price_per_unit=-min([0.,*marks]))
        results[name]=result
    original,opposite=results['original'],results['opposite']
    observations=[]
    if context['round_trip_cost_per_unit'] is None: observations.append('COST_ASSUMPTION_UNKNOWN')
    if not context['levels']: observations.append('LEVEL_CONTEXT_UNAVAILABLE')
    elif any(level['near_reference'] for level in context['levels']):
        observations.append('CONFIRMED_LEVEL_NEAR_REFERENCE')
    else: observations.append('NO_SAVED_LEVEL_NEAR_REFERENCE')
    if original['status']=='CLOSED':
        observations.append('ORIGINAL_'+original['exit_reason']+'_OBSERVED')
        if (original['gross_price_pnl_per_unit']>0 and original['net_price_pnl_per_unit'] is not None
                and original['net_price_pnl_per_unit']<=0):
            observations.append('PRICE_GAIN_CONSUMED_BY_ASSUMED_COSTS')
    if original['result']=='LOSS' and opposite['result']=='LOSS': observations.append('BOTH_DIRECTIONS_LOST')
    if original['result']=='LOSS' and opposite['result']=='WIN': observations.append('OPPOSITE_WON_IN_PAIRED_REPLAY')
    report=dict(status='TRADE_REVIEW_HYPOTHESES_ONLY',candidate_id=context['candidate_id'],
        symbol=context['symbol'],strategy_version=context['strategy_version'],
        decision_sha256=expected_decision_sha256,as_of_msc=as_of_msc,
        quote_sha256=sha256(_encode(ticks)).hexdigest(),outcomes=results,observations=observations,
        levels=context['levels'],market_regime=context['market_regime'],
        entry_thesis=context['entry_thesis'],
        causal_explanation_verified=False,quote_completeness_verified=False,
        cost_verified=False,account_pnl_available=False,automatic_rule_update=False,
        strategy_promoted=False,execution_allowed=False)
    encoded=_encode(report); pin=sha256(encoded).hexdigest()
    _write_exclusive(root/('review-'+pin+'.json'),encoded)
    return dict(report,review_sha256=pin)
