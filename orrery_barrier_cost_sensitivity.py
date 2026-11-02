"""Offline cost-threshold analysis for closed first-touch TP/SL events.

Assumes exact planned 1R stop, a per-trade target R, and explicit *hypothetical*
round-trip cost in R. Does not assert fills, gaps, commissions or net USD PnL.
Unresolved outcomes invalidate all-cohort expectancy.
"""
from math import isfinite,fsum

def compare(records, *, estimated_cost_r):
    if (type(estimated_cost_r) not in (int,float) or
        not isfinite(estimated_cost_r) or estimated_cost_r<0 or
        not isinstance(records,list) or len(records)>100000):
        raise ValueError('Explicit finite hypothetical cost R and bounded records required')
    wins=losses=unresolved=0
    values=[]
    for r in records:
        if not isinstance(r,dict) or r.get('execution_allowed') is not False:
            raise ValueError('Research-only records required')
        status=r.get('status'); target_r=r.get('target_r')
        if type(target_r) not in (int,float) or not isfinite(target_r) or target_r<=0:
            raise ValueError('Explicit target-to-stop risk ratio required')
        if status=='TP_FIRST':
            wins+=1;values.append(target_r-estimated_cost_r)
        elif status=='SL_FIRST':
            losses+=1;values.append(-1-estimated_cost_r)
        elif status in ('CENSORED_HORIZON','AMBIGUOUS_SAME_BAR'):
            unresolved+=1
        else: raise ValueError('Unknown barrier outcome')
    resolved=wins+losses
    gross_expected_r=(fsum(r['target_r'] if r['status']=='TP_FIRST' else -1
                          for r in records if r['status'] in ('TP_FIRST','SL_FIRST'))/resolved
                      if resolved else None)
    return dict(status='HYPOTHETICAL_R_COST_SENSITIVITY_ONLY',
        tp_first=wins,sl_first=losses,unresolved=unresolved,
        estimated_cost_r=estimated_cost_r,
        resolved_only_gross_mean_r=gross_expected_r,
        resolved_only_cost_adjusted_mean_r=fsum(values)/resolved if resolved else None,
        full_cohort_cost_adjusted_mean_r=fsum(values)/resolved if resolved and not unresolved else None,
        actual_net_expectancy_r=None,actual_profit_usd=None,
        broker_fees_verified=False,gaps_and_fills_verified=False,
        execution_allowed=False)
