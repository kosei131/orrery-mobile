"""Review one opening-spread filter on the existing Gold breakout cohort."""
from datetime import datetime, timezone
from hashlib import sha256
from math import isclose, isfinite
import json

from orrery_gold_channel_breakout import summarize

MAX_SPREAD_FRACTION = 0.10


def spread_group(row):
    risk = row.get('initial_risk_price')
    if risk is None:
        return 'UNKNOWN'
    stop_range = row['stop_range_price']
    if not isfinite(risk) or not isfinite(stop_range) or risk <= 0 or stop_range <= 0:
        raise ValueError('Positive finite risk and stop range required')
    spread = risk - stop_range
    if spread < 0 and not isclose(risk, stop_range, abs_tol=1e-9, rel_tol=0):
        raise ValueError('Negative implied opening spread')
    limit = MAX_SPREAD_FRACTION * risk
    return 'PASS' if spread <= limit or isclose(spread, limit, abs_tol=1e-9, rel_tol=0) else 'FILTERED'


def review(raw):
    source = json.loads(raw)
    if source['status'] != 'EXPLORATORY_XAUUSD_STANDALONE_CHANNEL_BREAKOUT':
        raise ValueError('Existing breakout evidence required')
    rows = sorted(source['records'], key=lambda row: row['at_utc'])
    groups = [(row, spread_group(row)) for row in rows]
    monthly = {}
    for month in source['by_utc_month']:
        subset = [(row, group) for row, group in groups
                  if datetime.fromtimestamp(row['at_utc'], timezone.utc).strftime('%Y-%m') == month]
        monthly[month] = {'baseline': summarize([row for row, _ in subset])}
        for group in ('PASS', 'FILTERED', 'UNKNOWN'):
            monthly[month][group] = summarize([row for row, label in subset if label == group])
    return dict(source_sha256=sha256(raw).hexdigest(), max_spread_fraction=MAX_SPREAD_FRACTION,
                by_utc_month=monthly, out_of_sample=False, account_return_pct=None,
                execution_allowed=False, adoption_allowed=False)
