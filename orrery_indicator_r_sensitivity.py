"""Matched, descriptive TP/SL R sensitivity by predeclared ADX/EMA cohort.

Requires explicitly supplied hypothetical cost R, target R, and a completed
outcome clock. Excludes leaking boundary outcomes. Does not certify an edge.
"""
from math import isfinite, fsum
from orrery_barrier_cost_sensitivity import compare

def compare_regimes(rows, *, split_at, cost_r, min_resolved=30):
    if (type(split_at) is not int or type(min_resolved) is not int or min_resolved<1
        or type(cost_r) not in (int,float) or not isfinite(cost_r) or cost_r<0
        or not isinstance(rows,list) or len(rows)>100000):
        raise ValueError('Explicit research settings required')
    buckets={};seen=set()
    for row in rows:
        t=row.get('decision_at'); o=row.get('outcome')
        adx=row.get('adx_at_decision');direction=row.get('ema_direction_at_decision')
        target=row.get('target_r')
        if (type(t) is not int or t in seen or not isinstance(o,dict)
            or o.get('status') not in ('TP_FIRST','SL_FIRST','AMBIGUOUS_SAME_BAR','CENSORED_HORIZON')
            or o.get('execution_allowed') is not False
            or type(adx) not in (int,float) or not isfinite(adx) or not 0<=adx<=100
            or direction not in ('UP','DOWN','FLAT')
            or type(target) not in (int,float) or not isfinite(target) or target<=0):
            raise ValueError('Causal canonical cohort row required')
        seen.add(t)
        end=o.get('observed_at')
        if type(end) is not int or end<=t:
            raise ValueError('Bounded outcome clock required')
        part=('EXCLUDED_BOUNDARY' if t<split_at<=end else
              'TRAIN' if t<split_at else 'HOLDOUT')
        regime='ADX_LT_20' if adx<20 else 'ADX_20_TO_25' if adx<25 else 'ADX_GE_25'
        buckets.setdefault((part,regime,direction),[]).append(
            dict(status=o['status'],target_r=target,execution_allowed=False))
    result=[]
    for (part,regime,direction),events in sorted(buckets.items()):
        stat=compare(events,estimated_cost_r=cost_r)
        n=stat['tp_first']+stat['sl_first']
        result.append(dict(partition=part,adx_regime=regime,ema_direction=direction,
            total=len(events),resolved=n,unresolved=stat['unresolved'],
            enough_resolved=n>=min_resolved,
            resolved_only_hypothetical_cost_adjusted_mean_r=stat['resolved_only_cost_adjusted_mean_r'],
            full_cohort_hypothetical_cost_adjusted_mean_r=stat['full_cohort_cost_adjusted_mean_r']
                if n>=min_resolved and part!='EXCLUDED_BOUNDARY' else None,
            verified_net_expectancy_r=None))
    return dict(status='INDICATOR_R_SENSITIVITY_RESEARCH_ONLY',cost_r_assumed=cost_r,
        cohorts=result,holdout_edge_verified=False,
        trade_rule_recommended=False,execution_allowed=False)
