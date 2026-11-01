"""Structural-candidate exit study, NOT an executable strategy or portfolio test."""
from lsr02 import hypothesis_targets
from lsr02_context import analyze
from lsr02_exits import finite, simulate
from lsr02_replay import replay

POLICIES = ('A_sweep_range_full', 'A_sweep_range_partial',
            'B_rr_full', 'B_rr_partial')


def outcome_summary(outcomes):
    """Descriptive CLOSED candidate outcomes; no account balance or DD claim."""
    closed = [o for o in outcomes if o['status'] == 'CLOSED']
    values = [o['completed_net_usd'] for o in closed]
    profit = sum(v for v in values if v > 0)
    loss = -sum(v for v in values if v < 0)
    rs = [o['realized_r'] for o in closed]
    win_rs = [r for r in rs if r > 0]
    loss_rs = [r for r in rs if r < 0]
    return dict(closed=len(closed), open=sum(o['status'] == 'OPEN' for o in outcomes),
                skipped=sum(o['status'] == 'SKIP' for o in outcomes),
                completed_net_usd=sum(values),
                expectancy_usd=sum(values)/len(values) if values else None,
                win_rate=sum(v > 0 for v in values)/len(values) if values else None,
                profit_factor=profit/loss if loss else None,
                expectancy_r=sum(rs)/len(rs) if rs else None,
                average_win_r=sum(win_rs)/len(win_rs) if win_rs else None,
                average_loss_r=sum(loss_rs)/len(loss_rs) if loss_rs else None)


def study(symbol, h4, m15, m5, *, as_of, buffer, risk_usd,
          round_trip_cost_usd, per_exit_cost_usd, partial_r, partial_fraction,
          lifetime=3600, left=2, right=2, regime_config=None, context_config=None):
    """Once per first RETEST, assume entry at its close; simulate later bars.

    A measurement is explicitly the triggering 15m sweep candle's high-low.
    B is 2.6 times initial stop distance. Partial target = partial_r * distance.
    Fixed USD risk for comparison only. Guards remain unverified. Candidate
    outcomes can overlap: aggregate sums are NOT an investable equity curve.
    """
    if (not all(finite(v) for v in (risk_usd, round_trip_cost_usd,
                                   per_exit_cost_usd, partial_r, partial_fraction))
            or risk_usd <= 0 or partial_r <= 0
            or min(round_trip_cost_usd, per_exit_cost_usd) < 0
            or not 0 < partial_fraction < 1):
        raise ValueError('Explicit valid research sizing and exit settings required')
    if context_config is not None:
        if not isinstance(context_config, dict) or set(context_config) != {'tenkan', 'kijun', 'span_b', 'shift'}:
            raise ValueError('Explicit cloud parameters required')
        analyze([], as_of=as_of, interval=300, left=left, right=right, **context_config)
    trace = replay(symbol, h4, m15, m5, as_of=as_of, buffer=buffer,
                   lifetime=lifetime, left=left, right=right,
                   regime_config=regime_config)
    five = {b['close_time']: b for b in m5}
    fifteen = {b['close_time']: b for b in m15}
    candidates = []
    current = None
    for row in trace:
        if row['state'] == 'SWEEP' and (current is None or current['invalidated_at'] is not None):
            source = fifteen[row['at']]
            current = dict(id=f"{symbol}:{row['at']}:{row['side']}",
                           side=row['side'], sweep_at=row['at'],
                           stop=row['stop'], sweep_range=source['high']-source['low'],
                           entry_at=None, entry=None, poi=None, policies={},
                           invalidated_at=None, reason='NO_RETEST',
                           guard_status='BLOCKED_UNVERIFIED_GUARDS',
                           execution_allowed=False)
            candidates.append(current)
        if current is None:
            continue
        if row['state'] == 'INVALID':
            current['invalidated_at'] = row['at']
            if current['entry_at'] is None:
                current['reason'] = row['reason']
            continue
        if row['state'] != 'RETEST' or current['entry_at'] is not None:
            continue
        entry = five[row['at']]['close']
        current.update(entry_at=row['at'], entry=entry, poi=row['poi'],
                       reason='HYPOTHETICAL_RETEST_CLOSE')
        if context_config is not None:
            current['entry_context'] = {
                label: analyze([b for b in stream if b['close_time'] <= row['at']],
                    as_of=row['at'], interval=interval, left=left, right=right, **context_config)
                for label, stream, interval in (('4H', h4, 14400), ('15m', m15, 900), ('5m', m5, 300))}
        sign = 1 if current['side'] == 'BUY' else -1
        distance = sign*(entry-current['stop'])
        # replay should already ensure no stop touch on entry candle.
        if distance <= 0 or current['sweep_range'] <= 0:
            raise ValueError('Invalid candidate geometry')
        targets = hypothesis_targets(current['side'], entry, current['stop'], current['sweep_range'])
        future = [b for b in m5 if b['close_time'] > row['at']]
        for name, target in (('A_sweep_range', targets['A_range_2_6']),
                             ('B_rr', targets['B_gross_rr_2_6'])):
            for kind in ('full', 'partial'):
                key = name+'_'+kind
                partial_target = entry+sign*partial_r*distance
                invalid = target <= 0 or sign*(target-entry) <= 0
                if kind == 'partial':
                    invalid = invalid or partial_target <= 0 or sign*(target-partial_target) <= 0
                if invalid:
                    current['policies'][key] = dict(status='SKIP',
                        reason='INVALID_OR_UNORDERED_TARGET', completed_net_usd=None)
                    continue
                levels = [(target, 1)] if kind == 'full' else [
                    (partial_target, partial_fraction), (target, 1-partial_fraction)]
                current['policies'][key] = simulate(future, side=current['side'],
                    entry=entry, sl=current['stop'], entry_at=row['at'], as_of=as_of,
                    interval=300, targets=levels, risk_usd=risk_usd,
                    round_trip_cost_usd=round_trip_cost_usd,
                    per_exit_cost_usd=per_exit_cost_usd)
    entered = [c for c in candidates if c['entry_at'] is not None]
    paired = [c for c in entered if all(c['policies'][p]['status'] == 'CLOSED' for p in POLICIES)]
    return dict(status='HYPOTHETICAL_CANDIDATE_STUDY', symbol=symbol,
                strategy_identity='LSR02_INDEPENDENT_HYPOTHESES',
                rule_2_6_status='UNRESOLVED_AUTHOR_DEFINITION',
                data_source='CALLER_PROVIDED_UNVERIFIED', execution_allowed=False,
                entry_assumption='FIRST_RETEST_CLOSE',
                measurement_A='TRIGGERING_15M_SWEEP_CANDLE_HIGH_MINUS_LOW',
                C_undefined=None, risk_usd=risk_usd,
                round_trip_cost_usd=round_trip_cost_usd,
                per_exit_cost_usd=per_exit_cost_usd,
                partial_r=partial_r, partial_fraction=partial_fraction,
                candidates=candidates, not_entered=len(candidates)-len(entered),
                summaries={p: outcome_summary([c['policies'][p] for c in entered]) for p in POLICIES},
                paired_completed_candidate_ids=[c['id'] for c in paired],
                paired_summaries={p: outcome_summary([c['policies'][p] for c in paired]) for p in POLICIES},
                summary_basis='INDEPENDENT_CANDIDATE_OUTCOMES_MAY_OVERLAP',
                portfolio_metrics_available=False)
