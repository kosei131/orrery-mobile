# SPDX-License-Identifier: GPL-3.0-only
# HalfTrend algorithm copyright (c) 2021-present Alex Orekhov (everget).
# Python research adaptation and confirmed-bar guards: ORRERY FX, 2026-10-29.
# See research_refs/halftrend/COPYING and source.json. No warranty.
"""Standalone closed-bar HalfTrend research; not a trading strategy.

Adapted from pinned everget Pine v6 source. No ORRERY core imports, orders,
automatic integration, trailing orders or claims of TradingView/MT5 parity.
"""
from hashlib import sha256
from json import dumps
from math import isfinite, fsum

SOURCE_REVISION = '8385cc421888bbf31f36407195796bc0eabafb19'
SOURCE_SHA256 = 'efa1915b4d0812d8126bd27c7667f9408e90aeed94988058b1b1edeaa23f4a3c'
AMPLITUDES = (2,4,6,8)


def calculate(bars, *, as_of, interval, amplitude=2, channel_deviation=2, enabled=False):
    if (type(enabled) is not bool or type(amplitude) is not int or amplitude not in AMPLITUDES
            or type(channel_deviation) is not int
            or not 0<=channel_deviation<=100 or type(interval) is not int or interval not in (300,900)
            or type(as_of) not in (int,float) or not isfinite(as_of) or as_of<0):
        raise ValueError('Explicit bounded HalfTrend research configuration required')
    base=dict(amplitude=amplitude,channel_deviation=channel_deviation,atr_period=100,
        interval=interval,source_revision=SOURCE_REVISION,source_sha256=SOURCE_SHA256,
        tradingview_parity_verified=False,mt5_parity_verified=False,
        nonrepainting_verified=False,market_edge_verified=False,execution_allowed=False)
    if not enabled: return dict(base,status='DISABLED',rows=[],signals=[])
    if not isinstance(bars,list) or len(bars)>10000:
        raise ValueError('Bounded closed OHLC history required')
    clean=[]; prior=None
    for bar in bars:
        if not isinstance(bar,dict) or bar.get('is_closed',True) is not True:
            raise ValueError('Closed OHLC record required')
        row={name:bar.get(name) for name in ('close_time','open','high','low','close')}
        if any(type(v) not in (int,float) or not isfinite(v) for v in row.values()):
            raise ValueError('Finite OHLC and closing clock required')
        at=row['close_time']
        if at<0 or at>as_of or (prior is not None and at-prior!=interval):
            raise ValueError('Future, duplicate, unordered or gapped bar')
        if not 0<row['low']<=min(row['open'],row['close'])<=max(row['open'],row['close'])<=row['high']:
            raise ValueError('Invalid OHLC geometry')
        clean.append(row); prior=at
    rows=[]; trend=0; next_trend=0; up=0.; down=0.; atr=None; true_ranges=[]
    max_low=clean[0]['low'] if clean else None
    min_high=clean[0]['high'] if clean else None
    for i,bar in enumerate(clean):
        window=clean[max(0,i-amplitude+1):i+1]
        high_price=max(b['high'] for b in window); low_price=min(b['low'] for b in window)
        high_ma=fsum(b['high'] for b in window)/amplitude if len(window)==amplitude else None
        low_ma=fsum(b['low'] for b in window)/amplitude if len(window)==amplitude else None
        previous=clean[i-1] if i else bar
        tr=max(bar['high']-bar['low'],abs(bar['high']-previous['close']),abs(bar['low']-previous['close']))
        true_ranges.append(tr)
        if i==99: atr=fsum(true_ranges)/100
        elif i>99: atr=(atr*99+tr)/100
        old_trend=trend; old_up=up; old_down=down
        if next_trend==1:
            max_low=max(low_price,max_low)
            if high_ma is not None and high_ma<max_low and bar['close']<previous['low']:
                trend=1; next_trend=0; min_high=high_price
        else:
            min_high=min(high_price,min_high)
            if low_ma is not None and low_ma>min_high and bar['close']>previous['high']:
                trend=0; next_trend=1; max_low=low_price
        flip=i>0 and trend!=old_trend
        if trend==0:
            up=old_down if flip else max_low if i==0 else max(max_low,old_up)
            line=up
        else:
            down=old_up if flip else min_high if i==0 else min(min_high,old_down)
            line=down
        half_atr=None if atr is None else atr/2
        width=None if atr is None else channel_deviation*half_atr
        signal=('BUY' if trend==0 else 'SELL') if flip and atr is not None else None
        result=dict(at=bar['close_time'],state='UP' if trend==0 else 'DOWN',
            line=line,atr=atr,atr_high=None if width is None else line+width,
            atr_low=None if width is None else line-width,signal=signal,
            signal_known_at=bar['close_time'] if signal else None,
            signal_close=bar['close'] if signal else None,
            ready=atr is not None and high_ma is not None,
            internal_transition=flip)
        if any(isinstance(v,float) and not isfinite(v) for v in result.values()):
            raise ValueError('HalfTrend arithmetic overflow')
        rows.append(result)
    return dict(base,status='HALFTREND_RESEARCH_ONLY' if len(clean)>=100 else 'INSUFFICIENT_HISTORY',
        rows=rows,signals=[r for r in rows if r['signal'] is not None],
        input_sha256=sha256(dumps(clean,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),
        history_start=clean[0]['close_time'] if clean else None,
        last_closed_at=clean[-1]['close_time'] if clean else None,
        history_seed_sensitive=True,
        caveat='Closed input only; finite-history seed and feed revisions can change results. No independent Pine/MT5 reference comparison or actual repaint observation yet.')


def compare_amplitudes(bars, *, as_of, interval, channel_deviation=2):
    results={str(a):calculate(bars,as_of=as_of,interval=interval,amplitude=a,
               channel_deviation=channel_deviation,enabled=True) for a in AMPLITUDES}
    return dict(status='AMPLITUDE_OBSERVATION_ONLY',results=results,
                best_amplitude=None,market_edge_verified=False,execution_allowed=False)
