"""Research-only chart levels and future scenario envelope.

No forecast candles or invented probabilities. Lines represent existing candidate
geometry, not verified targets or order instructions.
"""
from math import isfinite

def projection(plan, *, candidate_id, observed_close, as_of_s):
    if not isinstance(candidate_id,str) or not candidate_id or not isinstance(plan,dict):
        raise ValueError('Candidate plan required')
    side=plan.get('side')
    entry=plan.get('entry')
    stop=plan.get('stop')
    target=plan.get('target')
    known=plan.get('known_at_msc')
    if (side not in ('BUY','SELL') or
        any(type(v) not in (int,float) or not isfinite(v) or v<=0
            for v in (entry,stop,target,observed_close)) or
        type(known) is not int or type(as_of_s) is not int or
        known>as_of_s*1000 or observed_close<=0):
        raise ValueError('Finite closed-bar geometry and causal clock required')
    if not ((side=='BUY' and stop<entry<target) or
            (side=='SELL' and target<entry<stop)):
        raise ValueError('Invalid structural SL/TP geometry')
    risk=abs(entry-stop)
    reward=abs(target-entry)
    return dict(schema='ORRERY_RESEARCH_LEVELS_V1', candidate_id=candidate_id, side=side,
        as_of_s=as_of_s, observed_last_close=observed_close,
        lines=dict(entry_reference=entry,structural_sl=stop,reference_tp=target),
        reference_rr=reward/risk,
        forecast_candles=None,forecast_confidence=None,probability_tp_before_sl=None,
        expected_net_profit_usd=None,broker_costs_verified=False,
        status='RESEARCH_ONLY_NOT_A_PRICE_FORECAST',execution_allowed=False)
