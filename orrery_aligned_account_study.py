"""Compare TradingView plans on the exact catalog observations used for alignment."""
from hashlib import sha256
from math import isfinite

from lsr04_tick_archive import _encode
from lsr03_tick_study import load_catalog_ticks
from orrery_account_coverage_study import replay_continuous_window
from orrery_bar_quote_alignment import audit_session
from orrery_tradingview_study import INTERVALS, study


def compare(raw_csvs, settings, *, path, expected_catalog_sha256, max_gap_msc,
            price_tolerance, volume_min, volume_max, volume_step, pnl_quote,
            round_trip_cost_per_lot_usd, cost_source, slippage, max_ticks=500000,
            expected_start_s=None, expected_contract_size=None):
    """Run independent, single-session LSR02 and VHF03 model accounts."""
    report = study(raw_csvs, settings)
    result = dict(planning=report, alignment=None, accounts=None,
                  catalog_sha256=expected_catalog_sha256, execution_allowed=False)
    compiled = report['plans']
    if compiled is None:
        return dict(result, status=report['status'])

    loaded = load_catalog_ticks(path, expected_catalog_sha256=expected_catalog_sha256,
                                bar_source=settings['data_source'], as_of=settings['as_of_s'],
                                max_ticks=max_ticks)
    if loaded['blocked']:
        return dict(result, status='BLOCKED_GLOBAL_TICK_QUALITY', tick_audit=loaded['audit'])
    if (expected_contract_size is not None
            and loaded['audit']['broker_spec']['trade_contract_size'] != expected_contract_size):
        return dict(result, status='BLOCKED_CATALOG_CONTRACT_MISMATCH')
    start, end = loaded['start_msc'], loaded['end_msc']
    if start % 1000 or end % 1000:
        raise ValueError('Whole-second catalog boundaries required')
    if expected_start_s is not None and start != expected_start_s * 1000:
        return dict(result, status='BLOCKED_CATALOG_START_MISMATCH',
                    actual_start_s=start // 1000)
    ticks = loaded['ticks']
    alignment = audit_session(raw_csvs, settings, ticks, start_s=start // 1000,
                              end_s=end // 1000, max_gap_msc=max_gap_msc,
                              quote_symbol=loaded['symbol'], quote_source=settings['data_source'],
                              price_tolerance=price_tolerance)
    result['alignment'] = alignment
    if not alignment['aligned']:
        return dict(result, status='BLOCKED_BAR_QUOTE_ALIGNMENT')

    # Planning uses every confirmed bar. A bar that straddles the start
    # closes during replay, but was excluded from the full-bar OHLC audit.
    start_s = start // 1000
    crossing = sorted(
        frame for frame, audit in report['audit'].items()
        if audit['first_open_s'] < start_s < audit['last_close_s']
        and (start_s - audit['first_open_s']) % INTERVALS[frame]
    )
    if crossing:
        return dict(result, status='BLOCKED_BAR_CROSSES_SESSION_START',
                    crossing_frames=crossing)

    # Preserve exclusions for plans already known before this catalog began.
    plans = [p for p in compiled['plans'] if start <= p['known_at_msc'] < end]
    selected = [p for p in plans if compiled['groups'][p['id']] == 'VHF_PASS']
    accounts = {}
    for name, subset in (('LSR02', plans), ('VHF03', selected)):
        ids = {p['id'] for p in subset}
        replay = replay_continuous_window(
            ticks, subset, start_msc=start, end_msc=end, max_gap_msc=max_gap_msc,
            symbol=loaded['symbol'], initial_equity=3000, max_quotes=max_ticks,
            volume_min=volume_min, volume_max=volume_max, volume_step=volume_step,
            pnl_quote=pnl_quote, round_trip_cost_per_lot_usd=round_trip_cost_per_lot_usd,
            cost_source=cost_source, slippage=slippage,
            cancellations=[e for e in compiled['cancellations'] if e['id'] in ids])
        if replay['account'] is None:
            return dict(result, status=replay['status'], gap=replay['gap'])
        accounts[name] = replay['account']
    return dict(result, status='ALIGNED_SESSION_MODEL_ACCOUNTS', accounts=accounts,
                candidate_counts=dict(LSR02=len(plans), VHF03=len(selected)),
                out_of_window_candidates=len(compiled['plans']) - len(plans))


def compare_sessions(sessions, settings, **account_inputs):
    """Run a predeclared sequence of independent session comparisons.

    An absent dataset stays in the result. No balances, drawdowns, positions
    or risk stops are combined across independently initialized accounts.
    """
    if not isinstance(sessions, (list, tuple)) or not 1 <= len(sessions) <= 200:
        raise ValueError('Declare 1–200 ordered sessions')
    previous_end = 0
    required = {'start_s', 'end_s', 'raw_csvs', 'path', 'catalog_sha256'}
    for session in sessions:
        if not isinstance(session, dict) or session.keys() != required:
            raise ValueError('Exact session inputs required')
        start, end = session['start_s'], session['end_s']
        if type(start) is not int or type(end) is not int or not previous_end <= start < end:
            raise ValueError('Ordered, non-overlapping UTC sessions required')
        previous_end = end

    rows = []
    for session in sessions:
        start, end = session['start_s'], session['end_s']
        digest = session['catalog_sha256']
        if any(session[key] is None for key in ('raw_csvs', 'path', 'catalog_sha256')):
            result = dict(status='BLOCKED_MISSING_SESSION_INPUT', accounts=None)
        else:
            result = compare(session['raw_csvs'], dict(settings, as_of_s=end),
                             path=session['path'], expected_catalog_sha256=digest,
                             expected_start_s=start, **account_inputs)
        rows.append(dict(start_s=start, end_s=end, catalog_sha256=digest, result=result))
    completed = sum(row['result']['accounts'] is not None for row in rows)
    return dict(sessions=rows, completed_sessions=completed,
                blocked_sessions=len(rows) - completed, combined_accounts=None,
                execution_allowed=False)


def session_plan_sha256(sessions, settings, *, development_end_s,
                        valuation_source, **account_assumptions):
    """Fingerprint a protocol before holdout inputs are available."""
    if type(development_end_s) is not int or development_end_s < 0:
        raise ValueError('Declare the exclusive end of the development period')
    if not isinstance(valuation_source, str) or not valuation_source.strip():
        raise ValueError('Declare historical USD valuation source and version')
    windows = []
    previous_end = development_end_s
    for session in sessions:
        start, end = session['start_s'], session['end_s']
        if type(start) is not int or type(end) is not int or not previous_end <= start < end:
            raise ValueError('Holdout sessions must be ordered and follow development')
        windows.append([start, end])
        previous_end = end
    if not 1 <= len(windows) <= 200:
        raise ValueError('Declare 1–200 holdout sessions')
    # The replay derives its as-of timestamp from each declared window.
    config = {key: value for key, value in settings.items() if key != 'as_of_s'}
    protocol = dict(version=1, development_end_s=development_end_s, windows=windows,
                    settings=config, valuation_source=valuation_source,
                    account_assumptions=account_assumptions)
    return sha256(_encode(protocol)).hexdigest()


def compare_holdout(sessions, settings, *, expected_plan_sha256,
                    development_end_s, valuation_source, pnl_quote, **account_assumptions):
    """Replay only the declared protocol, using the separately supplied data."""
    digest = session_plan_sha256(sessions, settings, development_end_s=development_end_s,
                                valuation_source=valuation_source, **account_assumptions)
    if digest != expected_plan_sha256:
        raise ValueError('Holdout protocol SHA256 mismatch')
    result = compare_sessions(sessions, settings, pnl_quote=pnl_quote, **account_assumptions)
    return dict(result, plan_sha256=digest, development_end_s=development_end_s,
                valuation_source=valuation_source)


def xauusd_valuation_source(spec):
    """Validate and fingerprint an effective-dated linear USD contract record."""
    fields = {'source', 'start_s', 'end_s', 'contract_size'}
    if not isinstance(spec, dict) or spec.keys() != fields:
        raise ValueError('Exact XAUUSD contract evidence required')
    start, end, size = spec['start_s'], spec['end_s'], spec['contract_size']
    if (type(start) is not int or type(end) is not int or not 0 <= start < end
            or type(size) not in (int, float) or not isfinite(size) or size <= 0
            or not isinstance(spec['source'], str) or not spec['source'].strip()):
        raise ValueError('Effective UTC interval, positive contract size and source required')
    return 'XAUUSD_LINEAR_USD_V1:' + sha256(_encode(spec)).hexdigest()


def xauusd_cost_assumptions(spec):
    """Convert a dated fee record and a declared slippage model to replay inputs."""
    fields = {'fee_source', 'slippage_source', 'start_s', 'end_s',
              'round_trip_cost_per_lot_usd', 'slippage'}
    if not isinstance(spec, dict) or spec.keys() != fields:
        raise ValueError('Exact XAUUSD cost record required')
    start, end = spec['start_s'], spec['end_s']
    if type(start) is not int or type(end) is not int or not 0 <= start < end:
        raise ValueError('Effective UTC cost interval required')
    for key in ('fee_source', 'slippage_source'):
        if not isinstance(spec[key], str) or not spec[key].strip():
            raise ValueError('Fee and slippage sources required')
    for key in ('round_trip_cost_per_lot_usd', 'slippage'):
        value = spec[key]
        if type(value) not in (int, float) or not isfinite(value) or value < 0:
            raise ValueError('Explicit finite nonnegative fee and slippage required')
    return dict(cost_source='XAUUSD_COST_V1:' + sha256(_encode(spec)).hexdigest(),
                round_trip_cost_per_lot_usd=spec['round_trip_cost_per_lot_usd'],
                slippage=spec['slippage'])


def compare_xauusd_holdout(sessions, settings, *, contract_spec, expected_plan_sha256,
                           development_end_s, cost_spec=None, **account_assumptions):
    """Use one pinned linear USD contract for the full declared holdout."""
    spec = dict(contract_spec)
    source = xauusd_valuation_source(spec)
    if settings['symbol'] != 'XAUUSD':
        raise ValueError('Linear USD valuation here is limited to XAUUSD')
    if any(not spec['start_s'] <= row['start_s'] < row['end_s'] <= spec['end_s']
           for row in sessions):
        raise ValueError('XAUUSD contract evidence must cover all declared sessions')
    if cost_spec is not None:
        cost_inputs = xauusd_cost_assumptions(cost_spec)
        if cost_inputs.keys() & account_assumptions.keys():
            raise ValueError('Replay inputs cannot override the pinned cost record')
        if any(not cost_spec['start_s'] <= row['start_s'] < row['end_s'] <= cost_spec['end_s']
               for row in sessions):
            raise ValueError('XAUUSD cost record must cover all declared sessions')
        account_assumptions.update(cost_inputs)
    size = spec['contract_size']

    def pnl_quote(symbol, side, lots, entry, exit_price, at):
        if symbol != 'XAUUSD' or side not in ('BUY', 'SELL'):
            raise ValueError('XAUUSD and a known side required')
        direction = 1 if side == 'BUY' else -1
        return direction * (exit_price - entry) * lots * size

    result = compare_holdout(
        sessions, settings, expected_plan_sha256=expected_plan_sha256,
        development_end_s=development_end_s, valuation_source=source,
        pnl_quote=pnl_quote, expected_contract_size=size, **account_assumptions)
    return dict(result, contract_spec=spec, cost_spec=None if cost_spec is None else dict(cost_spec),
                broker_spec_authenticity_verified=False, cost_source_authenticity_verified=False)
