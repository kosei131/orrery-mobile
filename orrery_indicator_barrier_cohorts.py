"""Compare predeclared indicator regimes against future TP/SL first-hit labels.

All feature values must predate the outcome. This is descriptive, not a
forecast, broker quote, profit, trade recommendation or optimization result.
"""
from math import isfinite

def evaluate_cohorts(rows, *, split_at, min_count=30):
    if (type(split_at) is not int or type(min_count) is not int or
        min_count<1 or not isinstance(rows,list) or len(rows)>100000):
        raise ValueError('Bounded pinned retrospective records required')
    seen=set()
    groups={}
    for row in rows:
        if not isinstance(row,dict):raise ValueError('Record object required')
        at=row.get('decision_at')
        outcome=row.get('outcome')
        adx=row.get('adx_at_decision')
        atr=row.get('atr_at_decision')
        direction=row.get('ema_direction_at_decision')
        if (type(at) is not int or at in seen or not isinstance(outcome,dict)
            or outcome.get('status') not in ('TP_FIRST','SL_FIRST','AMBIGUOUS_SAME_BAR','CENSORED_HORIZON')
            or outcome.get('execution_allowed') is not False
            or type(adx) not in (int,float) or not isfinite(adx) or not 0<=adx<=100
            or type(atr) not in (int,float) or not isfinite(atr) or atr<=0
            or direction not in ('UP','DOWN','FLAT')):
            raise ValueError('Unique causal indicator/barrier record required')
        seen.add(at)
        event_at=outcome.get('observed_at')
        if event_at is not None and (type(event_at) is not int or event_at<=at):
            raise ValueError('Future outcome clock required')
        # The training cohort must not contain results from the untouched holdout.
        if at<split_at and (event_at is None or event_at>=split_at):
            partition='BOUNDARY_EXCLUDED'
        else:
            partition='TRAIN' if at<split_at else 'HOLDOUT'
        regime='ADX_LT_20' if adx<20 else ('ADX_20_TO_25' if adx<25 else 'ADX_GE_25')
        key=(partition,regime,direction)
        groups.setdefault(key,[]).append(outcome['status'])
    reports=[]
    for key in sorted(groups):
        events=groups[key]
        wins=events.count('TP_FIRST')
        losses=events.count('SL_FIRST')
        ambiguous=events.count('AMBIGUOUS_SAME_BAR')
        censored=events.count('CENSORED_HORIZON')
        resolved=wins+losses
        reports.append(dict(partition=key[0],adx_regime=key[1],ema_direction=key[2],
            total=len(events),tp_first=wins,sl_first=losses,ambiguous=ambiguous,censored=censored,
            resolved_only_tp_fraction=wins/resolved if resolved else None,
            sufficient_samples=resolved>=min_count,
            all_outcomes_resolved=resolved==len(events),
            full_cohort_win_rate=wins/len(events) if resolved==len(events) and events else None))
    return dict(status='INDICATOR_BARRIER_COHORTS_DESCRIPTIVE_ONLY',
        split_at=split_at,min_resolved=min_count,cohorts=reports,
        prediction_accuracy_verified=False,net_expectancy_usd=None,
        strategy_adopted=False,execution_allowed=False)
