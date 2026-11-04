# SPDX-License-Identifier: GPL-3.0-only
"""XAUUSD H4/M15/M5 A/B structural candidates, closed-bar research only.

A: follow confirmed H4 direction after opposite-side M15 liquidity sweep
and later M5 structure recovery.
B: counter H4 direction only after sweep of prior H4 outer extreme and
later M5 break in reversal direction. Separate cohorts, never mixed.
No trade fill or performance claim. All bars are as-of the detection close.
"""
from decimal import Decimal
from math import isfinite

STEP={'H4':14400,'M15':900,'M5':300}
SPEC={'h4_direction_bars':3,'m15_prior_extreme_bars':8,
      'm5_confirmation_bars':5,'m5_max_after_sweep':12,
      'stop_buffer_price_units':'0.10','min_target_room_r':'1.5'}
BUFFER=Decimal(SPEC['stop_buffer_price_units'])
ROOM=Decimal(SPEC['min_target_room_r'])


def _bars(series,tf,as_of):
    if not isinstance(series,(list,tuple)) or len(series)>10000:
        raise ValueError('Bounded closed OHLC required')
    prior=None
    for b in series:
        if not isinstance(b,dict) or set(b)!={'close_time','open','high','low','close'}:
            raise ValueError('OHLC schema mismatch')
        t=b['close_time']
        if type(t) is not int or t<0 or t%STEP[tf] or t>as_of:
            raise ValueError('Unclosed or unaligned candle')
        if prior is not None and t-prior!=STEP[tf]:
            raise ValueError('Gapped or reordered history')
        price=(b[k] for k in ('open','high','low','close'))
        if any(type(v) not in (int,float) or not isfinite(v) or v<=0 for v in price):
            raise ValueError('Finite positive OHLC required')
        if not b['low']<=min(b['open'],b['close'])<=max(b['open'],b['close'])<=b['high']:
            raise ValueError('Inconsistent OHLC')
        prior=t
    return series


def candidate(h4,m15,m5,*,as_of):
    if type(as_of) is not int or as_of<0 or as_of%300:
        raise ValueError('Closed M5 as-of required')
    h4=_bars(h4,'H4',as_of)
    m15=_bars(m15,'M15',as_of)
    m5=_bars(m5,'M5',as_of)
    if len(h4)<3 or len(m15)<9 or len(m5)<6 or m5[-1]['close_time']!=as_of:
        return None
    # No stale context: H4 completed within preceding four hours.
    if not (0<=as_of-h4[-1]['close_time']<14400):
        return None
    h=h4[-3:]
    is_up=h[0]['high']<h[1]['high']<h[2]['high'] and h[0]['low']<h[1]['low']<h[2]['low']
    is_down=h[0]['high']>h[1]['high']>h[2]['high'] and h[0]['low']>h[1]['low']>h[2]['low']
    if not (is_up or is_down):
        return None
    direction='UP' if is_up else 'DOWN'
    # Search backwards only across the fixed 60-minute window, with the M15
    # sweep confirmed BEFORE the current closed M5 confirmation.
    selected=None
    for i in range(len(m15)-1,7,-1):
        sweep=m15[i]
        clock=sweep['close_time']
        if clock>=as_of or as_of-clock>3600:
            continue
        if clock<h4[-1]['close_time']:
            continue
        prev=m15[i-8:i]
        floor=min(b['low'] for b in prev)
        ceil=max(b['high'] for b in prev)
        low_sweep=sweep['low']<floor and sweep['close']>floor
        high_sweep=sweep['high']>ceil and sweep['close']<ceil
        if not (low_sweep or high_sweep):
            continue
        # No overlapping sweep variants: select latest eligible event.
        selected=(sweep,low_sweep,high_sweep)
        break
    if selected is None:return None
    sweep,low_sweep,high_sweep=selected
    side='BUY' if low_sweep else 'SELL'
    # At least five closed M5 bars after the M15 sweep are not needed;
    # the structure reference consists of five bars BEFORE the current one.
    confirm=m5[-1]
    if confirm['close_time']<=sweep['close_time'] or confirm['close_time']-sweep['close_time']>3600:
        return None
    prior_five=m5[-6:-1]
    # Require the reference bars to have closed no later than signal time,
    # but disallow an M5 structure confirmation already broken at sweep time.
    earlier=[b for b in prior_five if b['close_time']<=sweep['close_time']]
    if not earlier:return None
    reference=max(b['high'] for b in earlier) if side=='BUY' else min(b['low'] for b in earlier)
    confirmed=(confirm['close']>reference and confirm['close']>confirm['open']
               if side=='BUY' else confirm['close']<reference and confirm['close']<confirm['open'])
    if not confirmed:return None
    after_sweep=[b for b in m5[:-1] if sweep['close_time']<b['close_time']<as_of]
    # No delayed duplicate candidate after an earlier confirming close; a
    # structure failure before confirmation permanently invalidates this sweep.
    if side=='BUY':
        if any(b['close']>reference or b['low']<=sweep['low'] for b in after_sweep):
            return None
    else:
        if any(b['close']<reference or b['high']>=sweep['high'] for b in after_sweep):
            return None
    family='A_CONTINUATION' if (side=='BUY')==is_up else 'B_COUNTER_SWEEP'
    # Reversal B demands a sweep beyond an earlier H4 outer extreme, not
    # just a local M15 breakout.
    if family=='B_COUNTER_SWEEP':
        outer=min(x['low'] for x in h4[-3:-1]) if side=='BUY' else max(x['high'] for x in h4[-3:-1])
        if not (sweep['low']<outer if side=='BUY' else sweep['high']>outer):
            return None
    entry=Decimal(str(confirm['close']))
    stop=Decimal(str(sweep['low']))-BUFFER if side=='BUY' else Decimal(str(sweep['high']))+BUFFER
    risk=entry-stop if side=='BUY' else stop-entry
    if risk<=0:return None
    # Target room is a BEFORE-known H4 extreme, not a fixed arbitrary take profit.
    room_level=max(x['high'] for x in h4[-3:]) if side=='BUY' else min(x['low'] for x in h4[-3:])
    room=Decimal(str(room_level))-entry if side=='BUY' else entry-Decimal(str(room_level))
    if room<ROOM*risk:return None
    return dict(candidate_id=f'{family}:{as_of}:{side}',family=family,side=side,
                known_at_utc=as_of,sweep_known_at_utc=sweep['close_time'],
                h4_direction=direction,confirmation_reference=str(reference),
                indicative_close=str(entry),structural_stop=str(stop),
                initial_risk_price=str(risk),known_room_price=str(room),
                indicative_room_r=str(room/risk),entry_quote_verified=False,
                fill_verified=False,net_expectancy_r=None,
                execution_allowed=False)
