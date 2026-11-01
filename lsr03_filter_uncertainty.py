"""Paired risk-day bootstrap of existing matched VHF research outcomes.

Daily sums are independent-candidate R, never account returns. No threshold
selection, new signal calculation, fills or order permission is implemented.
"""
from collections import Counter
from math import fsum, isfinite, isclose
from random import Random
from hashlib import sha256
from lsr04_tick_archive import _encode

STATUSES = {'CLOSED','OPEN','NO_NEXT_BAR','INVALID_STOP','NO_ENTRY_QUOTE',
            'OUTSIDE_TICK_COVERAGE','CANDIDATE_EXPIRED_BEFORE_FILL','INVALID_STRUCTURE'}


def evaluate(report, *, samples=2000, seed=0, boundary_utc_hour=10):
    if (type(samples) is not int or not 100 <= samples <= 10000
            or type(seed) is not int or not 0 <= seed < 2**32
            or type(boundary_utc_hour) is not int or not 0 <= boundary_utc_hour <= 23):
        raise ValueError('Explicit bounded resampling settings required')
    if (not isinstance(report, dict) or report.get('status') not in
            ('MATCHED_TICK_CANDIDATE_RESEARCH','HYPOTHETICAL_MATCHED_CANDIDATE_RESEARCH')
            or report.get('execution_allowed') is not False
            or report.get('market_edge_verified', False) is not False):
        raise ValueError('Read-only matched candidate research required')
    rows = report.get('rows')
    if not isinstance(rows, list) or len(rows) > 100000:
        raise ValueError('Bounded candidate rows required')
    symbol = report.get('symbol')
    if symbol is not None and symbol not in ('XAUUSD','USDJPY'):
        raise ValueError('Canonical report symbol required')
    seen = set(); days = {}; states = Counter(); unresolved = 0
    baseline = []; kept = []; excluded = []
    for row in rows:
        if not isinstance(row, dict): raise ValueError('Candidate record required')
        identity, group, status = (row.get(k) for k in ('id','group','status'))
        at = row.get('structural_at')
        if (not isinstance(identity, str) or not identity or identity in seen
                or group not in ('VHF_PASS','VHF_FILTERED') or status not in STATUSES
                or type(at) not in (int,float) or not isfinite(at) or at < 0):
            raise ValueError('Unique supported candidate and timestamp required')
        seen.add(identity); states[group+':'+status] += 1
        row_symbol = identity.split(':')[0]
        if row_symbol not in ('XAUUSD','USDJPY'):
            raise ValueError('Canonical candidate symbol required')
        if symbol is None: symbol = row_symbol
        if row_symbol != symbol: raise ValueError('Do not pool instruments')
        # Timestamp is the original structural decision clock, never exit time.
        day = int((at-boundary_utc_hour*3600)//86400)
        days.setdefault(day, [])
        if status != 'CLOSED':
            if 'net_r' in row: raise ValueError('Non-closed outcome cannot carry realized R')
            unresolved += 1
            continue
        value = row.get('net_r')
        if type(value) not in (int,float) or not isfinite(value):
            raise ValueError('Finite closed net R required; costs are already included')
        baseline.append(value)
        if group == 'VHF_PASS': kept.append(value)
        else:
            excluded.append(value)
            days[day].append(-value)  # paired filtered-minus-baseline outcome
    total = fsum(baseline); passed = fsum(kept); delta = -fsum(excluded)
    avoided = -fsum(x for x in excluded if x < 0)
    missed = fsum(x for x in excluded if x > 0)
    if not all(isfinite(x) for x in (total, passed, delta, avoided, missed)):
        raise ValueError('Outcome aggregation overflow')
    for key, expected in (('avoided_loss_r',avoided),('missed_profit_r',missed)):
        if key in report and (type(report[key]) not in (int,float)
                or not isfinite(report[key]) or not isclose(report[key], expected, rel_tol=1e-9, abs_tol=1e-9)):
            raise ValueError('Existing decomposition disagrees with candidate rows')
    daily = [fsum(days[day]) for day in sorted(days)]
    if len(daily)*samples > 5000000:
        raise ValueError('Resampling work budget exceeded')
    warnings = ['INSPECTED_DATA_NOT_OUT_OF_SAMPLE','CANDIDATE_R_NOT_ACCOUNT_RETURN',
                'OBSERVED_CANDIDATE_DAYS_ONLY_NOT_A_FULL_CALENDAR',
                'WITHIN_DAY_CLUSTERING_ONLY_SERIAL_DEPENDENCE_MAY_REMAIN',
                'NO_MULTIPLE_TESTING_CORRECTION']
    interval = None
    if unresolved: warnings.append('NON_CLOSED_OUTCOMES_EFFECT_UNKNOWN')
    if len(daily) < 2: warnings.append('INSUFFICIENT_RISK_DAYS')
    if len(daily) < 20: warnings.append('SMALL_CLUSTER_SAMPLE')
    if rows and not unresolved and len(daily) >= 2:
        rng = Random(seed)
        # Resample complete daily paired effects; do not split correlated entries.
        means = sorted(fsum(rng.choice(daily) for _ in daily)/len(daily)
                       for _ in range(samples))
        def percentile(p):
            index = (len(means)-1)*p
            low = int(index); fraction = index-low
            return means[low]*(1-fraction)+means[min(low+1,len(means)-1)]*fraction
        interval = dict(method='PAIRED_RISK_DAY_PERCENTILE_BOOTSTRAP',
                        confidence_level=.95, lower=percentile(.025), upper=percentile(.975),
                        unit='INDEPENDENT_CANDIDATE_R_PER_OBSERVED_RISK_DAY')
    return dict(status='DESCRIPTIVE_FILTER_UNCERTAINTY_ONLY', symbol=symbol, candidates=len(rows),
        closed=len(baseline), non_closed=unresolved, states=dict(sorted(states.items())),
        observed_risk_days=len(daily), boundary_utc_hour=boundary_utc_hour,
        observed_closed_only=dict(baseline_total_net_r=total, filtered_total_net_r=passed,
            avoided_loss_r=avoided, missed_profit_r=missed, delta_candidate_r=delta),
        full_candidate_effect_r=delta if rows and not unresolved else None,
        mean_delta_per_observed_risk_day=fsum(daily)/len(daily) if daily and not unresolved else None,
        interval=interval, samples=samples, seed=seed, warnings=warnings,
        source_report_sha256=sha256(_encode(report)).hexdigest(),
        broker_costs_verified=False, market_edge_verified=False,
        portfolio_metrics_available=False, filter_adopted=False, execution_allowed=False)
