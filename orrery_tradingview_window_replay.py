"""Independent contiguous-window LSR research and gross price-reference R.

No price interpolation, assumed trading calendar, Bid/Ask fabrication, account
return or order authority. Gaps reset candidate state; this is not a continuous
session-aware backtest. Price-reference entry assumes the confirmed RETEST close.
"""
import argparse
from hashlib import sha256
from io import BytesIO
import json
from math import fsum, isfinite
from pathlib import Path
import zipfile

from orrery_tradingview_bundle_audit import audit_bundle, _bars, _utc, _iso, FRAMES
from lsr03_account_study import build_account_plans
from lsr02_exits import simulate
from lsr02_structure import detect
from lsr03_vhf import calculate
from lsr03_learning_rollup import _sequence as candidate_sequence

PARAMETERS = {'buffer', 'target_r', 'period', 'min_vhf', 'left', 'right', 'lifetime'}


def _parameters(p):
    if not isinstance(p, dict) or set(p) != PARAMETERS:
        raise ValueError('Exact explicit strategy parameters required')
    if (any(type(p[k]) is not int or not 1 <= p[k] <= 100 for k in ('left', 'right'))
            or type(p['period']) is not int or not 2 <= p['period'] <= 100
            or any(type(p[k]) not in (int, float) or not isfinite(p[k]) or p[k] <= 0
                   for k in ('buffer', 'target_r', 'lifetime'))
            or type(p['min_vhf']) not in (int, float) or not isfinite(p['min_vhf'])
            or not 0 <= p['min_vhf'] <= 1):
        raise ValueError('Invalid explicit strategy parameters')


def _groups(rows, step):
    groups = []
    for row in rows:
        if not groups or row['close_time'] != groups[-1][-1]['close_time'] + step:
            groups.append([])
        groups[-1].append(row)
    return groups


def _aligned_windows(frames):
    keys = list(FRAMES)
    groups = [_groups(frames[f], FRAMES[f]) for f in keys]
    indices = [0, 0, 0]
    while all(indices[i] < len(groups[i]) for i in range(3)):
        chosen = [groups[i][indices[i]] for i in range(3)]
        start = max(g[0]['close_time'] - FRAMES[f] for g, f in zip(chosen, keys))
        end = min(g[-1]['close_time'] for g in chosen)
        if start < end:
            m5 = [b for b in chosen[0] if start <= b['close_time'] - 300 and b['close_time'] <= end]
            # Context may include earlier bars from its OWN contiguous group,
            # but never from a prior group or later than the window's end.
            m15 = [b for b in chosen[1] if b['close_time'] <= end]
            h4 = [b for b in chosen[2] if b['close_time'] <= end]
            if m5 and m15 and h4:
                if any(len(b) > 2000 for b in (m5, m15, h4)):
                    raise ValueError('Replay frame budget exceeded')
                yield dict(start_s=start, end_s=end, h4=h4, m15=m15, m5=m5)
        for i, g in enumerate(chosen):
            if g[-1]['close_time'] == end:
                indices[i] += 1


def _reference_outcome(plan, m5, end):
    at = plan['known_at_msc'] // 1000
    reference = next(b['close'] for b in m5 if b['close_time'] == at)
    future = [b for b in m5 if b['close_time'] > at]
    # Unit risk is a mathematical scaling device. Strip every USD/net field:
    # costs are unavailable, NOT verified zero. Only gross reference R survives.
    result = simulate(future, side=plan['side'], entry=reference, sl=plan['stop'],
        entry_at=at, as_of=end, interval=300, targets=[(plan['target'], 1)],
        risk_usd=1, round_trip_cost_usd=0, per_exit_cost_usd=0)
    fill = result['fills'][0] if result['fills'] else None
    ambiguous = False
    if fill and fill['reason'] == 'STOP_FIRST':
        b = next(b for b in future if b['close_time'] == fill['at'])
        ambiguous = (b['high'] >= plan['target'] if plan['side'] == 'BUY' else b['low'] <= plan['target'])
    status = ('AMBIGUOUS_INTRABAR' if ambiguous else
              'CLOSED_REFERENCE' if result['status'] == 'CLOSED' else 'CENSORED_AT_WINDOW_END')
    value = result['realized_r'] if status == 'CLOSED_REFERENCE' else None
    return dict(entry_reference=reference, entry_reference_at_s=at,
        reference_status=status, reference_r=value,
        reference_r_exit_at=None if value is None else fill['at'] * 1000,
        exit_reference_price=None if value is None else fill['price'],
        exit_reference_reason=None if value is None else fill['reason'],
        stop_first_reference_r=result['realized_r'] if ambiguous else None,
        intrabar_exit_clock_unknown=bool(fill), net_r=None, profit_usd=None)


def _one_window(window, parameters):
    compiled = build_account_plans('XAUUSD', window['h4'], window['m15'], window['m5'],
                                   as_of=window['end_s'], **parameters)
    rows = [dict(plan=plan, vhf_group=compiled['groups'][plan['id']],
                 **_reference_outcome(plan, window['m5'], window['end_s']))
            for plan in compiled['plans']]
    for row in rows:
        at = row['entry_reference_at_s']; plan = row['plan']
        context = [b for b in window['h4'] if b['close_time'] <= at]
        fifteen = [b for b in window['m15'] if b['close_time'] <= at]
        h = detect(context, as_of=at, interval=14400, left=parameters['left'], right=parameters['right'])
        v = calculate(fifteen, period=parameters['period'], as_of=at, interval=900)
        row['entry_context'] = dict(h4_trend=h['trend'], vhf_status=v['status'],
            vhf_value=v['value'], vhf_slope=v['slope'],
            invalidating_sweep_extreme=plan['stop'] + (parameters['buffer'] if plan['side'] == 'BUY' else -parameters['buffer']),
            causal_explanation_verified=False,
            thesis='EXISTING_HTF_DIRECTION_M15_SWEEP_M5_CONFIRM_RETEST')
    return rows, compiled['omitted']


def _summary(rows):
    values = [r['reference_r'] for r in rows if r['reference_r'] is not None]
    loss = -fsum(v for v in values if v < 0); profit = fsum(v for v in values if v > 0)
    complete = bool(rows) and len(values) == len(rows)
    return dict(candidates=len(rows), closed_reference=len(values),
        censored=sum(r['reference_status'] == 'CENSORED_AT_WINDOW_END' for r in rows),
        ambiguous=sum(r['reference_status'] == 'AMBIGUOUS_INTRABAR' for r in rows),
        reference_wins=sum(v > 0 for v in values), reference_losses=sum(v < 0 for v in values),
        mean_closed_gross_reference_r=fsum(values) / len(values) if values else None,
        profit_factor_closed_gross_reference=profit / loss if loss else None,
        all_candidates_reference_resolved=complete,
        total_all_candidates_gross_reference_r=fsum(values) if complete else None,
        closed_reference_sequence=candidate_sequence(rows, 'reference_r'),
        net_expectancy_r=None, account_return_pct=None, account_max_dd_usd=None, actual_profit_usd=None)


def replay_bundle(raw, parameters, *, max_windows=100, max_work=5000000):
    _parameters(parameters)
    if (type(max_windows) is not int or not 1 <= max_windows <= 1000
            or type(max_work) is not int or not 1 <= max_work <= 10000000):
        raise ValueError('Bounded replay budgets required')
    audit = audit_bundle(raw)
    if (audit['manifest_mismatches'] or audit['common_range']['elapsed_seconds'] == 0
            or any(c['mismatch_count'] or not c['checked_complete_parent_bars']
                   for c in audit['common_range_nominal_aggregation'].values())):
        raise ValueError('Common-range nominal consistency required; inspect bundle audit')
    start = _utc(audit['common_range']['start_open_utc']); end = _utc(audit['common_range']['end_nominal_close_utc'])
    frames = {}
    with zipfile.ZipFile(BytesIO(raw)) as z:
        for frame, step in FRAMES.items():
            rows, _ = _bars(z.read(frame + '.csv'), step, _utc(audit['cutoff_utc']))
            frames[frame] = [dict(close_time=r['at'] + step,
                **{k: float(r[k]) for k in ('open', 'high', 'low', 'close')})
                for r in rows if start <= r['at'] and r['at'] + step <= end]
    windows = []
    for window in _aligned_windows(frames):
        if len(windows) >= max_windows:
            raise ValueError('Replay window budget exceeded')
        windows.append(window)
    if not windows:
        raise ValueError('No common contiguous windows or replay window budget exceeded')
    work = sum(len(w['m5']) * sum(len(w[f]) for f in ('m5', 'm15', 'h4')) for w in windows)
    if work > max_work or any(len(w[f]) > 2000 for w in windows for f in ('m5', 'm15', 'h4')):
        raise ValueError('Replay work budget exceeded')
    candidates = []; omitted = []; window_reports = []; seen = set()
    for i, w in enumerate(windows):
        rows, skipped = _one_window(w, parameters)
        for row in rows:
            if row['plan']['id'] in seen or len(seen) >= 1000:
                raise ValueError('Duplicate candidate or candidate budget exceeded')
            seen.add(row['plan']['id']); candidates.append(dict(window=i, **row))
        omitted.extend(dict(window=i, **row) for row in skipped)
        window_reports.append(dict(index=i, start_open_utc=_iso(w['start_s']), end_close_utc=_iso(w['end_s']),
            bars={f: len(w[f]) for f in ('h4', 'm15', 'm5')}, candidates=len(rows)))
    selected = [r for r in candidates if r['vhf_group'] == 'VHF_PASS']
    root = Path(__file__).resolve().parent
    names = (Path(__file__).name, 'orrery_tradingview_bundle_audit.py', 'lsr03_account_study.py',
             'lsr03_adapter.py', 'lsr02_replay.py', 'lsr02_structure.py', 'lsr02_sequence.py',
             'lsr03_vhf.py', 'lsr02_exits.py', 'lsr02.py', 'lsr02_regime.py', 'lsr03_learning_rollup.py')
    return dict(status='EXPLORATORY_WINDOW_RESET_GROSS_REFERENCE_ONLY', zip_sha256=audit['zip_sha256'],
        code_sha256={n: sha256((root / n).read_bytes()).hexdigest() for n in names},
        parameters=parameters, parameters_optimized=False, common_range=audit['common_range'],
        windows=window_reports, candidates=candidates, omitted=omitted, estimated_work=work,
        common_m5_bars=len(frames['5m']), replayed_m5_bars=sum(len(w['m5']) for w in windows),
        summaries=dict(LSR02=_summary(candidates), VHF03=_summary(selected)),
        bundle_audit=audit, source_authenticated=False, partial_h4_session_bars_verified=False,
        calendar_verified=False, warmup_before_common_range_used=False,
        candidate_state_carried_across_windows=False, continuous_backtest_complete=False,
        intrabar_fills_verified=False, bid_ask_and_fees_available=False, account_risk_controls_applied=False,
        actual_profit_usd=None, market_edge_verified=False, six_month_backtest_complete=False,
        excluded_modules=['LSR01_INDEPENDENT_PATH', 'REVERSAL04', 'HALFTREND05', 'UNDEFINED_2_6'],
        strategy_promoted=False, execution_allowed=False,
        caveat='Existing LSR02/VHF03 per observed contiguous window; resets change coverage. RETEST close is a hypothetical price reference. Unknown/ambiguous exits stay None. R is not net account PnL; no margin, sizing, portfolio/daily/streak stops or carry evaluation. No strategy adoption.')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('zip', type=Path); p.add_argument('--parameters', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); a = p.parse_args(argv)
    with a.zip.open('rb') as f:
        raw = f.read(16 * 1024 * 1024 + 1)
    with a.parameters.open('rb') as f:
        config = f.read(65537)
    if len(config) > 65536:
        raise ValueError('Parameter file budget exceeded')
    result = replay_bundle(raw, json.loads(config))
    with a.output.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False); f.write('\n')
    print(json.dumps(result['summaries'], allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
