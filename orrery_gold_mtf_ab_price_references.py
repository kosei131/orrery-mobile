# SPDX-License-Identifier: GPL-3.0-only
"""Read-only Gold M5 structural-stop and capped-target *price references*.

This is a separate exploratory A/B outcome study, not actual trades.
No authenticated Bid/Ask, broker fees, spreads, slippage, or realized PnL.
The first OPEN after the known M5 confirmation is a hypothetical reference,
not proof of an executable fill. Never interpolate missing candles or infer
which barrier touched first within the same M5 candle.
"""
from bisect import bisect_right
from collections import Counter
from decimal import Decimal, InvalidOperation

STEP=300
HORIZON=24
REWARD=Decimal('1.5')
VALID_FAMILIES=('A_CONTINUATION','B_COUNTER_SWEEP')
RESOLVED=('STOP_REFERENCE','TARGET_REFERENCE','TIMEOUT_REFERENCE','ADVERSE_OPEN_REFERENCE',
          'FAVORABLE_OPEN_CAPPED_REFERENCE')


def _price(x):
    try:
        if isinstance(x,bool) or x is None:
            raise ValueError('Finite positive price required')
        d=Decimal(str(x))
    except (InvalidOperation,TypeError):
        raise ValueError('Invalid decimal price') from None
    if not d.is_finite() or d<=0:
        raise ValueError('Finite positive price required')
    return d


def evaluate(bars,candidates,*,buy_ask_open_by_clock=None):
    """Use Bid exit bars with an optional Ask entry at the same M5 open clock."""
    if not isinstance(bars,(list,tuple)) or not isinstance(candidates,(list,tuple)):
        raise ValueError('Finite bar and candidate arrays required')
    if len(bars)>200000 or len(candidates)>10000:
        raise ValueError('Research bounds exceeded')
    clocks=[]; normalized=[]
    for b in bars:
        if not isinstance(b,dict) or set(b)!={'close_time','open','high','low','close'}:
            raise ValueError('Exact M5 OHLC fields required')
        t=b['close_time']
        if type(t) is not int or t<0 or t%STEP or (clocks and t<=clocks[-1]):
            raise ValueError('Strict sorted aligned closed bars required')
        row={k:_price(b[k]) for k in ('open','high','low','close')}
        if not row['low']<=min(row['open'],row['close'])<=max(row['open'],row['close'])<=row['high']:
            raise ValueError('Invalid OHLC')
        clocks.append(t); normalized.append(row)
    result=[];used=set()
    for c in candidates:
        if not isinstance(c,dict):
            raise ValueError('Candidate must be a mapping')
        ident=c.get('candidate_id');family=c.get('family');side=c.get('side')
        at=c.get('known_at_utc')
        if (not isinstance(ident,str) or not ident or ident in used or
            family not in VALID_FAMILIES or side not in ('BUY','SELL') or
            type(at) is not int or at<0 or at%STEP or c.get('fill_verified') is not False
            or c.get('execution_allowed') is not False):
            raise ValueError('Invalid immutable candidate')
        used.add(ident)
        stop=_price(c.get('structural_stop'))
        signal_price=_price(c.get('indicative_close'))
        room=_price(c.get('known_room_price'))
        implied_level=signal_price+room if side=='BUY' else signal_price-room
        if side=='SELL' and implied_level<=0:
            raise ValueError('Invalid known SELL target obstacle')
        j=bisect_right(clocks,at)
        state='CENSORED_NO_NEXT_M5'
        value=None;entry=None;exit_clock=None;target=None;risk=None
        paired = buy_ask_open_by_clock is not None
        if paired and side != 'BUY':
            raise ValueError('Ask-entry comparison supports BUY only')
        if j<len(clocks) and clocks[j]==at+STEP and paired and at not in buy_ask_open_by_clock:
            state='CENSORED_NO_PAIRED_ASK_OPEN'
        elif j<len(clocks) and clocks[j]==at+STEP:
            entry=(_price(buy_ask_open_by_clock[at]) if paired else normalized[j]['open'])
            if paired and entry < normalized[j]['open']:
                raise ValueError('Crossed Ask/Bid entry reference')
            risk=(entry-stop if side=='BUY' else stop-entry)
            if risk<=0:
                state='CENSORED_INVALID_OPEN_RISK'
            else:
                # Do not set a TP past the pre-signal H4 obstacle.
                raw_target=entry+REWARD*risk if side=='BUY' else entry-REWARD*risk
                target=min(raw_target,implied_level) if side=='BUY' else max(raw_target,implied_level)
                if (target<=entry if side=='BUY' else target>=entry):
                    state='CENSORED_NO_TARGET_ROOM_AT_OPEN'
                else:
                    state='CENSORED_DATA_END'
                    for k in range(HORIZON):
                        pos=j+k
                        if pos>=len(clocks):
                            break
                        expected=at+(k+1)*STEP
                        if clocks[pos]!=expected:
                            state='CENSORED_M5_GAP'
                            break
                        b=normalized[pos]
                        exit_clock=clocks[pos]
                        adverse_open=b['open']<=stop if side=='BUY' else b['open']>=stop
                        favorable_open=b['open']>=target if side=='BUY' else b['open']<=target
                        stop_hit=b['low']<=stop if side=='BUY' else b['high']>=stop
                        target_hit=b['high']>=target if side=='BUY' else b['low']<=target
                        if (k>0 or paired) and adverse_open:
                            state='ADVERSE_OPEN_REFERENCE'
                            value=((b['open']-entry)/risk if side=='BUY' else (entry-b['open'])/risk)
                            break
                        if k>0 and favorable_open:
                            state='FAVORABLE_OPEN_CAPPED_REFERENCE'
                            value=((target-entry)/risk if side=='BUY' else (entry-target)/risk)
                            break
                        if stop_hit and target_hit:
                            state='AMBIGUOUS_SAME_M5'
                            break
                        if stop_hit:
                            state='STOP_REFERENCE';value=Decimal('-1');break
                        if target_hit:
                            state='TARGET_REFERENCE'
                            value=((target-entry)/risk if side=='BUY' else (entry-target)/risk)
                            break
                        if k==HORIZON-1:
                            state='TIMEOUT_REFERENCE'
                            value=((b['close']-entry)/risk if side=='BUY' else (entry-b['close'])/risk)
        result.append(dict(candidate_id=ident,family=family,side=side,
            known_at_utc=at,entry_open_reference=(str(entry) if entry is not None else None),
            structural_stop=str(stop),target_reference=(str(target) if target is not None else None),
            state=state,reference_r=(float(value) if value is not None else None),
            exit_m5_close=exit_clock))
    cohorts={}
    for family in VALID_FAMILIES:
        rows=[r for r in result if r['family']==family]
        resolved=[r['reference_r'] for r in rows if r['reference_r'] is not None]
        pos=sum(v>0 for v in resolved)
        gross_pos=sum(v for v in resolved if v>0)
        gross_neg=-sum(v for v in resolved if v<0)
        cohorts[family]=dict(candidates=len(rows),resolved=len(resolved),
            unresolved=len(rows)-len(resolved),positive=pos,
            reference_win_pct=(round(100*pos/len(resolved),4) if resolved else None),
            reference_mean_r=(round(sum(resolved)/len(resolved),6) if resolved else None),
            reference_pf=(round(gross_pos/gross_neg,6) if gross_neg>0 else None),
            outcomes=dict(Counter(r['state'] for r in rows)))
    return dict(status='PUBLIC_OHLC_AB_PRICE_REFERENCES_NOT_BROKER_PNL',
        horizon_m5_bars=HORIZON,target_r_cap=1.5,
        risk_source='structural_sweep_stop; next M5 open indicative only',
        target_source='min/max of 1.5R and pre-signal H4 obstacle',
        records=result,cohorts=cohorts,price_basis_verified=False,
        execution_fills_verified=False,fees_verified=False,spread_verified=False,
        slippage_verified=False,out_of_sample=False,actual_win_rate_pct=None,
        net_expectancy_r=None,account_return_pct=None,adoption_allowed=False,
        execution_allowed=False)
