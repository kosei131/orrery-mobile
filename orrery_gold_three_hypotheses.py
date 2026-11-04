# SPDX-License-Identifier: GPL-3.0-only
"""Three separate closed-M15 Gold entry *hypotheses*, never executable orders.

Inputs are contiguous confirmed 15-minute integer-price OHLC candles. The
lookback is fixed at 20 bars. All signals are known at current bar close;
execution, slippage, fills, R and profitability are NOT inferred. Designed
for independent prospective research, not a redefinition of formal LSR02.
"""
from collections import Counter

STEP=900
LOOKBACK=20
MAX_BARS=150000
FAMILIES=('TREND_CONTINUATION','SWEEP_REVERSAL','FAILED_BREAK_REENTRY')


def scan(bars):
    if not isinstance(bars,(list,tuple)) or len(bars)>MAX_BARS:
        raise ValueError('Bounded candle sequence required')
    prior=None
    for b in bars:
        if not isinstance(b,dict) or set(b)!= {'close_time','open','high','low','close'}:
            raise ValueError('Exact closed-M15 OHLC fields required')
        t=b['close_time']
        if any(type(v) is not int for v in b.values()) or t<0 or t%STEP:
            raise ValueError('Integer aligned closed candles required')
        if (min(b['open'],b['close'])<b['low'] or
            max(b['open'],b['close'])>b['high'] or b['low']<=0):
            raise ValueError('Inconsistent OHLC')
        if prior is not None and t<=prior:
            raise ValueError('Strict raw time order required')
        prior=t
    out=[]
    for i in range(LOOKBACK+1,len(bars)):
        prev=bars[i-1]; now=bars[i]
        # Never bridge a missing 15-minute candle, including across a weekend.
        history=bars[i-LOOKBACK-1:i+1]
        if any(b['close_time']-a['close_time']!=STEP for a,b in zip(history,history[1:])):
            continue
        anchor=bars[i-LOOKBACK-1:i-1]  # 20 bars before previous candle
        prev_hi=max(b['high'] for b in anchor)
        prev_lo=min(b['low'] for b in anchor)
        current_history=bars[i-LOOKBACK:i]
        breakout_hi=max(b['high'] for b in current_history)
        breakout_lo=min(b['low'] for b in current_history)
        three=bars[i-3:i]
        hypotheses=[]
        if (now['close']>breakout_hi and now['close']>now['open']
            and three[0]['close']<three[1]['close']<three[2]['close']):
            hypotheses.append(('TREND_CONTINUATION','BUY',breakout_hi))
        if (now['close']<breakout_lo and now['close']<now['open']
            and three[0]['close']>three[1]['close']>three[2]['close']):
            hypotheses.append(('TREND_CONTINUATION','SELL',breakout_lo))
        if (prev['low']<prev_lo and prev['close']>prev_lo
            and now['close']>prev['high'] and now['close']>now['open']):
            hypotheses.append(('SWEEP_REVERSAL','BUY',prev_lo))
        if (prev['high']>prev_hi and prev['close']<prev_hi
            and now['close']<prev['low'] and now['close']<now['open']):
            hypotheses.append(('SWEEP_REVERSAL','SELL',prev_hi))
        if (prev['close']<prev_lo and prev_lo<=now['close']<=prev_hi
            and now['close']>now['open']):
            hypotheses.append(('FAILED_BREAK_REENTRY','BUY',prev_lo))
        if (prev['close']>prev_hi and prev_lo<=now['close']<=prev_hi
            and now['close']<now['open']):
            hypotheses.append(('FAILED_BREAK_REENTRY','SELL',prev_hi))
        for family,side,level in hypotheses:
            out.append(dict(candidate_id=f'M15:{now["close_time"]}:{family}:{side}',
                            family=family,side=side,signal_known_at=now['close_time'],
                            research_level_scaled=level,entry_price_scaled=None,
                            stop_price_scaled=None,fill_verified=False,
                            outcome_r=None,execution_allowed=False))
    counts=dict(Counter(s['family'] for s in out))
    return dict(status='CAUSAL_M15_HYPOTHESES_ONLY',symbol='XAUUSD',
                bar_seconds=STEP,lookback_bars=LOOKBACK,signals=out,
                signal_count_by_family={f:counts.get(f,0) for f in FAMILIES},
                price_source_sha256=None,real_price_results_verified=False,
                out_of_sample=False,net_expectancy_r=None,
                account_return_pct=None,execution_allowed=False)
