# SPDX-License-Identifier: GPL-3.0-only
"""Reconcile exploratory Gold censor scenarios to pinned GitHub evidence."""
from math import isclose, isfinite

def reconcile(source, scenario):
    if (source.get('raw_source_sha256') != scenario.get('source_sha256')
        or scenario.get('status') != 'CENSORED_OUTCOME_SCENARIO_ONLY'
        or scenario.get('assumed_spread_price_units') != 0.6
        or scenario.get('artificial_unknown_outcome_scenarios_r') != [-1, 1.5]
        or scenario.get('adoption_allowed') is not False
        or scenario.get('actual_net_expectancy_r') is not None):
        raise ValueError('Pinned source/scenario policy mismatch')
    models=source['models']
    rows=scenario['results']
    if not isinstance(rows,list) or len(rows)!=len(models) or {r['name'] for r in rows}!=set(models):
        raise ValueError('Missing or extra model')
    for row in rows:
        original=models[row['name']]['0.6']['entry_outcomes']
        total=original['total_r']
        n=original['candidates']
        resolved=original['resolved_outcomes']
        unknown=n-resolved
        if any(type(v) is not int for v in (n,resolved,unknown)) or n<=0 or unknown<0:
            raise ValueError('Invalid candidate denominator')
        for key, expected in (
            ('candidates',n),('resolved',resolved),('unresolved',unknown),
            ('wins',original['wins'])):
            if type(row[key]) is not int or row[key]!=expected:
                raise ValueError('Cohort count changed')
        for key, expected in (
            ('total_resolved_r',total),
            ('scenario_all_unknown_minus_1r_mean',(total-unknown)/n),
            ('scenario_all_unknown_plus_1_5r_mean',(total+1.5*unknown)/n)):
            actual=row[key]
            if type(actual) not in (int,float) or not isfinite(actual) or not isclose(actual,expected,abs_tol=1e-10):
                raise ValueError('Scenario arithmetic changed')
    return dict(reconciled_models=len(rows),historical_only=True,
                broker_net_expectancy_verified=False,adoption_allowed=False)
