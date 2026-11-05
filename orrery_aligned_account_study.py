"""Compare TradingView plans on the exact catalog observations used for alignment."""
from lsr03_tick_study import load_catalog_ticks
from orrery_account_coverage_study import replay_continuous_window
from orrery_bar_quote_alignment import audit_session
from orrery_tradingview_study import study


def compare(raw_csvs, settings, *, path, expected_catalog_sha256, max_gap_msc,
            price_tolerance, volume_min, volume_max, volume_step, pnl_quote,
            round_trip_cost_per_lot_usd, cost_source, slippage, max_ticks=500000):
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
    start, end = loaded['start_msc'], loaded['end_msc']
    if start % 1000 or end % 1000:
        raise ValueError('Whole-second catalog boundaries required')
    ticks = loaded['ticks']
    alignment = audit_session(raw_csvs, settings, ticks, start_s=start // 1000,
                              end_s=end // 1000, max_gap_msc=max_gap_msc,
                              quote_symbol=loaded['symbol'], quote_source=settings['data_source'],
                              price_tolerance=price_tolerance)
    result['alignment'] = alignment
    if not alignment['aligned']:
        return dict(result, status='BLOCKED_BAR_QUOTE_ALIGNMENT')

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
