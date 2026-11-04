# SPDX-License-Identifier: GPL-3.0-only
"""Conservative M15 price-touch study for three causal XAU entry hypotheses.

No broker Bid/Ask, fill, net PnL, or claim of edge. Entry is hypothetical at
the next contiguous closed candle's OPEN after a known signal; this is NOT
proof that this price could have been filled. Fixed SL = 6 GOLD price units,
TP = 1.5R, timeout = eight M15 candles. No data repairs or future signals.
"""
from collections import Counter
from orrery_gold_three_hypotheses import STEP,FAMILIES

SCALE=1000000
STOP_DISTANCE=6*SCALE
TP_NUMERATOR=3
TP_DENOMINATOR=2
MAX_HOLD_BARS=8


def measure(candles, signals):
    if not isinstance(candles,(list,tuple)) or not isinstance(signals,(list,tuple)):
        raise ValueError('Fixed candles and signals required')
    if len(candles)>150000 or len(signals)>150000:
        raise ValueError('Bounded sequences required')
    by_close={}
    prev=None
    for c in candles:
        if not isinstance(c,dict) or set(c)!={'close_time','open','high','low','close'}:
            raise ValueError('Exact candles required')
        if any(type(x) is not int for x in c.values()):
            raise ValueError('Integer closed candles required')
        t=c['close_time']
        if t<0 or t%STEP or t in by_close or (prev is not None and t<=prev):
            raise ValueError('Ordered unique M15 bars required')
        if c['low']<=0 or not c['low']<=min(c['open'],c['close'])<=max(c['open'],c['close'])<=c['high']:
            raise ValueError('Invalid OHLC')
        by_close[t]=c
        prev=t
    ids=set()
    records=[]
    for signal in signals:
        if not isinstance(signal,dict):
            raise ValueError('Signal mapping required')
        ident=signal.get('candidate_id')
        family=signal.get('family')
        side=signal.get('side')
        at=signal.get('signal_known_at')
        if (not isinstance(ident,str) or not ident or ident in ids or family not in FAMILIES
            or side not in ('BUY','SELL') or type(at) is not int or at not in by_close):
            raise ValueError('Fixed known, unique signals required')
        if signal.get('entry_price_scaled') is not None or signal.get('outcome_r') is not None:
            raise ValueError('Only unpriced pretrade hypotheses allowed')
        ids.add(ident)
        entrybar=by_close.get(at+STEP)
        state='CENSORED_NEXT_BAR_MISSING'
        outcome=None
        entry=None
        exit_clock=None
        if entrybar is not None:
            entry=entrybar['open']
            stop=entry-STOP_DISTANCE if side=='BUY' else entry+STOP_DISTANCE
            target=entry+(TP_NUMERATOR*STOP_DISTANCE//TP_DENOMINATOR) if side=='BUY' else entry-(TP_NUMERATOR*STOP_DISTANCE//TP_DENOMINATOR)
            state='CENSORED_DATA_END'
            for n in range(1,MAX_HOLD_BARS+1):
                bar=by_close.get(at+n*STEP)
                if bar is None:
                    state='CENSORED_M15_GAP'
                    break
                # Gap opening is recorded as a reference observation, not exact
                # stop execution or target fill.
                adverse=(bar['open']<=stop if side=='BUY' else bar['open']>=stop)
                favorable=(bar['open']>=target if side=='BUY' else bar['open']<=target)
                sl=(bar['low']<=stop if side=='BUY' else bar['high']>=stop)
                tp=(bar['high']>=target if side=='BUY' else bar['low']<=target)
                exit_clock=bar['close_time']
                if adverse:
                    state='STOP_GAP_OPEN_REFERENCE'
                    outcome=((bar['open']-entry)/STOP_DISTANCE if side=='BUY' else (entry-bar['open'])/STOP_DISTANCE)
                    break
                if favorable:
                    state='TARGET_GAP_OPEN_REFERENCE_CAPPED'
                    outcome=1.5
                    break
                if sl and tp:
                    state='AMBIGUOUS_SAME_M15'
                    break
                if sl:
                    state='STOP_TOUCH_REFERENCE'
                    outcome=-1.0
                    break
                if tp:
                    state='TARGET_TOUCH_REFERENCE'
                    outcome=1.5
                    break
                if n==MAX_HOLD_BARS:
                    state='TIMEOUT_CLOSE_REFERENCE'
                    outcome=((bar['close']-entry)/STOP_DISTANCE if side=='BUY' else (entry-bar['close'])/STOP_DISTANCE)
        records.append(dict(candidate_id=ident,family=family,side=side,
                            signal_known_at=at,hypothetical_entry_open_scaled=entry,
                            state=state,reference_r=outcome,exit_bar_close_time=exit_clock))
    cohorts={}
    for family in FAMILIES:
        subset=[r for r in records if r['family']==family]
        known=[r['reference_r'] for r in subset if r['reference_r'] is not None]
        positive=sum(x>0 for x in known)
        cohorts[family]=dict(candidates=len(subset),reference_resolved=len(known),
            unresolved=len(subset)-len(known),positive=positive,
            observed_positive_pct=(100*positive/len(known) if known else None),
            mean_reference_r=(sum(known)/len(known) if known else None),
            status_counts=dict(Counter(r['state'] for r in subset)))
    return dict(status='UNVERIFIED_M15_OHLC_REFERENCE_STUDY_ONLY',
                entry_rule='next contiguous M15 open after signal close',
                price_basis='publisher OHLC not authenticated Bid/Ask',
                stop_distance_price_units=6,target_r=1.5,horizon_bars=8,
                no_fees_or_slippage_modeled=True,
                same_bar_dual_touch_censored=True,
                candidates=records,cohorts=cohorts,net_expectancy_r=None,
                actual_win_rate_pct=None,account_return_pct=None,
                backtest_ready=False,adoption_allowed=False,execution_allowed=False)
