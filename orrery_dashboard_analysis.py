"""Read-only dashboard composition; never infer account risk from missing SLs."""
from lsr02_snapshot_overlay import export_snapshot, FRAMES
from orrery_indicator_diagnostics import diagnostics
from lsr02_overlay_export import overlay as history_overlay


def analyze(snapshot, now):
    result = dict(status='WAIT', execution_allowed=False, automatic_orders=False,
                  expected_net_r=None, account_sl_risk=None, charts=[])
    historical = snapshot.get('status') == 'PUBLIC_HISTORY_RESEARCH'
    if snapshot.get('status') != 'READ_ONLY_DEMO' and not historical:
        result['status'] = 'SIMULATED_TEST_DATA'
        return result
    for chart in snapshot.get('charts', []):
        item = dict(symbol=chart['symbol'], timeframe=chart['timeframe'],
                    status='UNAVAILABLE', levels=[], indicators=None,
                    reference_plans=[])
        try:
            if historical:
                interval = FRAMES[item['timeframe']]
                raw = [dict(close_time=int(b['time'])+interval,
                            **{k:b[k] for k in ('open','high','low','close')}) for b in chart['bars']]
                overlay = history_overlay(raw, symbol=item['symbol'], interval=interval,
                    as_of=raw[-1]['close_time'], tenkan=9, kijun=26, span_b=52, shift=26,
                    source='PUBLIC_UNVERIFIED_OHLC', source_verified=False)
            else:
                overlay = export_snapshot(snapshot, symbol=item['symbol'],
                                          timeframe=item['timeframe'], now=now)
            bars = [dict(close_time=int(b['close_time']),
                         **{k: b[k] for k in ('open', 'high', 'low', 'close')})
                    for b in overlay['bars']]
            indicators = diagnostics(bars, as_of=bars[-1]['close_time'] if historical else int(now), interval=FRAMES[item['timeframe']])
            item.update(status='RESEARCH_LEVELS_ONLY', levels=overlay['levels'],
                        indicators=indicators, reasons=overlay['reasons'])
            # Opposing confirmed pivots define review scenarios, not LSR entry signals.
            support = next((v['price'] for v in overlay['levels']
                            if v['kind'] == 'NEAREST_SUPPORT'), None)
            resistance = next((v['price'] for v in overlay['levels']
                               if v['kind'] == 'NEAREST_RESISTANCE'), None)
            entry = bars[-1]['close']
            if support is not None and resistance is not None and support < entry < resistance:
                for side, sl, tp in [('BUY', support, resistance), ('SELL', resistance, support)]:
                    item['reference_plans'].append(dict(side=side, reference_entry=entry,
                        structural_sl=sl, structural_tp=tp,
                        gross_reward_risk=abs(tp-entry)/abs(entry-sl),
                        basis='LAST_CLOSED_PRICE_CONFIRMED_PIVOTS_NOT_ENTRY_SIGNAL',
                        costs_verified=False, expected_net_r=None, execution_allowed=False))
        except (ValueError, KeyError, TypeError):
            pass
        result['charts'].append(item)
    return result
