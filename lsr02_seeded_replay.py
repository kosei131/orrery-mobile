"""Deterministic, synthetic-only scenario replay with immutable seeded data.
NOT the ORRERY LSR trading algorithm or a real 6-month market backtest.
"""
import hashlib
import json
import random
from datetime import datetime, timezone

def simulate(*,seed=260427,steps=1500,initial_equity=10000.0,risk_fraction=.0025,
             reward_r=2.6,avoid_range=False,loss_streak_stop=None):
    if type(seed) is not int or type(steps) is not int or not 100<=steps<=100000:
        raise ValueError("Invalid seed or steps")
    if not (0<risk_fraction<=.01 and 0<reward_r<=10 and initial_equity>0):
        raise ValueError("Invalid synthetic research settings")
    if loss_streak_stop is not None and (type(loss_streak_stop) is not int or loss_streak_stop<1):\n        raise ValueError('Positive loss streak stop required')\n    rng=random.Random(seed)
    # Independent held-out regime process, not generated from market prices.
    regimes=["TREND","RANGE","VOLATILE"]
    candles=[]
    price=2000.
    for i in range(steps):
        regime=regimes[(i//100)%3]
        drift={"TREND":.16,"RANGE":0.,"VOLATILE":-.02}[regime]
        shock=rng.gauss(drift,{"TREND":.6,"RANGE":.45,"VOLATILE":1.2}[regime])
        old=price;price=max(1.,price+shock)
        candles.append(dict(t=i,open=round(old,5),close=round(price,5),
            high=round(max(old,price)+.1,5),low=round(min(old,price)-.1,5),
            regime=regime))
    # One-bar entry signal based exclusively on previous completed candle.
    # Next bar resolves TP or SL conservatively if both touched.
    equity=initial_equity;peak=equity;max_dd=0.;ledger=[];loss_streak=0;halted_at=None
    for i in range(1,len(candles)):
        previous=candles[i-1];current=candles[i]
        if previous["close"]<=previous["open"]:continue
        if avoid_range and previous["regime"]=="RANGE":continue
        entry=previous["close"];distance=.3
        stop=entry-distance;target=entry+distance*reward_r
        if current["low"]<=stop: outcome=-1.
        elif current["high"]>=target:outcome=reward_r
        else:continue # No exit hit; never count unclosed trades as wins.
        # Independent one-bar trade result, not an executable overlapping portfolio.
        risk=equity*risk_fraction
        cost=.08*risk
        pnl=risk*outcome-cost
        equity+=pnl;peak=max(peak,equity);max_dd=max(max_dd,peak-equity)\n        loss_streak=loss_streak+1 if pnl<0 else 0\n        if loss_streak_stop is not None and loss_streak>=loss_streak_stop:halted_at=i
        ledger.append(dict(signal_at=i-1,exit_at=i,regime=previous["regime"],
                           outcome_r=outcome,net_pnl_usd=round(pnl,6),
                           equity_usd=round(equity,6)))
    payload=json.dumps(candles,sort_keys=True,separators=(",",":")).encode()
    wins=sum(t["net_pnl_usd"]>0 for t in ledger)
    return dict(status="SYNTHETIC_RESEARCH_ONLY",execution_allowed=False,
       seed=seed,steps=steps,price_series_sha256=hashlib.sha256(payload).hexdigest(),
       parameters=dict(initial_equity=initial_equity,risk_fraction=risk_fraction,
                       reward_r=reward_r,avoid_range=avoid_range,cost_r=.08,\n                       loss_streak_stop=loss_streak_stop),
       halted_at=halted_at,trades=len(ledger),wins=wins,win_rate=wins/len(ledger) if ledger else None,
       final_equity_usd=round(equity,2),
       net_pnl_usd=round(equity-initial_equity,2),
       sampled_max_drawdown_usd=round(max_dd,2),
       ledger=ledger,price_series=candles)

def compare(**kwargs):
    baseline=simulate(**kwargs,avoid_range=False)
    filtered=simulate(**kwargs,avoid_range=True)
    if baseline["price_series_sha256"]!=filtered["price_series_sha256"]:
        raise AssertionError("Price series must match")
    return dict(status="SYNTHETIC_COMPARISON_NOT_REAL_BACKTEST",
                baseline=baseline,filtered=filtered,
                execution_allowed=False)
