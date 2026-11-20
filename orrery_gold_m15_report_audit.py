# SPDX-License-Identifier: GPL-3.0-only
"""Integrity audit for three-family XAU M15 reference-outcome reports.

This rejects corrupted counts and ensures censored outcomes are not silently
treated as trades. It does not certify broker prices, fills or profitability.
"""
from collections import Counter
from math import isclose, isfinite
from orrery_gold_three_hypotheses import FAMILIES

REFERENCE_STATUSES={
 'STOP_GAP_OPEN_REFERENCE','TARGET_GAP_OPEN_REFERENCE_CAPPED',
 'STOP_TOUCH_REFERENCE','TARGET_TOUCH_REFERENCE','TIMEOUT_CLOSE_REFERENCE'
}

def audit(report):
    if (not isinstance(report,dict)
        or report.get('status')!='UNVERIFIED_M15_OHLC_REFERENCE_STUDY_ONLY'
        or report.get('execution_allowed') is not False
        or report.get('adoption_allowed') is not False
        or report.get('net_expectancy_r') is not None
        or report.get('actual_win_rate_pct') is not None
        or report.get('account_return_pct') is not None
        or report.get('backtest_ready') is not False):
        raise ValueError('Research-only status and unknown actual PnL required')
    records=report.get('candidates')
    cohorts=report.get('cohorts')
    if not isinstance(records,list) or not isinstance(cohorts,dict) or set(cohorts)!=set(FAMILIES):
        raise ValueError('All cohorts and candidate records required')
    seen=set()
    for r in records:
        ident=r.get('candidate_id')
        if not isinstance(ident,str) or not ident or ident in seen:
            raise ValueError('Unique candidate IDs required')
        seen.add(ident)
        if r.get('family') not in FAMILIES:
            raise ValueError('Unknown family')
        v=r.get('reference_r')
        status=r.get('state')
        if (status in REFERENCE_STATUSES) != (type(v) in (int,float) and isfinite(v)):
            raise ValueError('Known/unknown result distinction changed')
        if status not in REFERENCE_STATUSES and status not in {
            'AMBIGUOUS_SAME_M15','CENSORED_NEXT_BAR_MISSING',
            'CENSORED_M15_GAP','CENSORED_DATA_END'}:
            raise ValueError('Unexpected outcome state')
    for name in FAMILIES:
        rows=[r for r in records if r['family']==name]
        resolved=[r['reference_r'] for r in rows if r['reference_r'] is not None]
        c=cohorts[name]
        states=dict(Counter(r['state'] for r in rows))
        if (type(c.get('candidates')) is not int or c['candidates']!=len(rows)
            or type(c.get('reference_resolved')) is not int or c['reference_resolved']!=len(resolved)
            or type(c.get('unresolved')) is not int or c['unresolved']!=len(rows)-len(resolved)
            or type(c.get('positive')) is not int or c['positive']!=sum(v>0 for v in resolved)
            or c.get('status_counts')!=states):
            raise ValueError('Cohort denominator or status accounting changed')
        expected_pct=100*sum(v>0 for v in resolved)/len(resolved) if resolved else None
        expected_mean=sum(resolved)/len(resolved) if resolved else None
        for key,expected in (('observed_positive_pct',expected_pct),('mean_reference_r',expected_mean)):
            actual=c.get(key)
            if expected is None:
                if actual is not None:raise ValueError('Unknown metric must be null')
            elif type(actual) not in (int,float) or not isfinite(actual) or not isclose(actual,expected,rel_tol=1e-12,abs_tol=1e-12):
                raise ValueError('Derived cohort metric inconsistent')
    return dict(candidate_count=len(records),
                reconciled_families=len(FAMILIES),
                reference_only=True,profitability_verified=False,
                execution_allowed=False)
