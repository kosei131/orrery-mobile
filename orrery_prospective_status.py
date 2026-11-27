# SPDX-License-Identifier: GPL-3.0-only
"""Clock-only acquisition bounds for the frozen pilot; no market observations."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from orrery_halftrend_holdout import decode_plan
from orrery_tradingview_bundle_audit import _utc, _iso

PLAN = Path(__file__).resolve().parent/'research_evidence/local-history-20261101/halftrend_prospective_plan_20261102.json'
PLAN_SHA256 = '580ec6b919f6da6e9adb8b0973f89f3af2112000dce56ca559899bd10803c434'


def acquisition_status(plan_raw, *, plan_sha256, now):
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError('Aware observation time required')
    p = decode_plan(plan_raw, plan_sha256)
    start = _utc(p['start_open_utc']); end = _utc(p['end_close_utc'])
    at = int(now.timestamp()); cutoff = max(start, min(at, end))
    phase = 'NOT_STARTED' if at < start else 'ENDED' if at >= end else 'IN_PROGRESS'
    # Do not floor to a UTC H4 grid: the actual feed/session alignment must be
    # supplied and audited, especially around DST. These are only inequalities.
    frames = {}
    for frame, seconds in (('5m',300),('15m',900),('4H',14400)):
        upper = cutoff-seconds
        frames[frame] = dict(interval_seconds=seconds,
            earliest_evaluation_open_utc=_iso(start),
            latest_possible_nominal_open_utc=_iso(upper) if at >= start and upper >= start else None,
            actual_bar_count=None, feed_grid_verified=False)
    hst = timezone(timedelta(hours=-10))
    local = lambda t: datetime.fromtimestamp(t, hst).isoformat()
    return dict(status='NO_PROSPECTIVE_INPUT_ATTACHED', phase=phase,
        observed_at_utc=now.astimezone(timezone.utc).isoformat(), plan_sha256=plan_sha256,
        start_open_utc=_iso(start), end_close_utc=_iso(end),
        start_hst=local(start), end_hst=local(end),
        closed_bar_cutoff_upper_bound_utc=_iso(cutoff) if at >= start else None,
        elapsed_calendar_seconds=max(0,min(at,end)-start), planned_calendar_seconds=end-start,
        frames=frames, source_declared=p['source_declared'],
        prospective_candidates=None, net_expectancy_r=None, account_return_pct=None,
        complete_session_coverage_verified=False, data_acquired=False,
        execution_allowed=False, adopted=False,
        limitation='Clock bounds only, not observed bars, session coverage or data availability. No prospective input attached to this view.')


def current_status(now=None):
    return acquisition_status(PLAN.read_bytes(), plan_sha256=PLAN_SHA256,
                              now=now or datetime.now(timezone.utc))
