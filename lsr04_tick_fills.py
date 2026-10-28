"""Research-only historical Bid/Ask paper exit: NO orders or live fills.

Entry at the first available quote at/after requested UTC millisecond time.
BUY opens at Ask and closes at Bid; SELL opens at Bid and closes at Ask.
Stops execute at the first available quote after crossing, including gaps.
Outcomes are price differences only; broker PnL requires contract/currency data.
"""
from math import isfinite

def market_exit_price(*, side, bid, ask, slippage):
    """Observed closing side plus adverse slippage; no quote interpolation."""
    if side not in ('BUY','SELL') or any(type(v) not in (int,float) or not isfinite(v)
            for v in (bid,ask,slippage)) or not 0<bid<=ask or slippage<0:
        raise ValueError('Invalid market exit quote')
    price=bid-slippage if side=='BUY' else ask+slippage
    if not isfinite(price) or price<=0:raise ValueError('Unrepresentable market exit')
    return price


def replay_exit(ticks,*,side,entry_after_msc,stop_price,target_price,slippage=0.):
    if side not in ("BUY","SELL") or type(entry_after_msc) not in (int,float) or not isfinite(entry_after_msc):
        raise ValueError("Bad side or entry timestamp")
    if any(type(x) not in (int,float) or not isfinite(x) or x<=0 for x in (stop_price,target_price)):
        raise ValueError("Positive stop/target required")
    if type(slippage) not in (int,float) or not isfinite(slippage) or slippage<0:
        raise ValueError("Invalid slippage")
    if not isinstance(ticks,list):raise ValueError("Ticks must be list")
    entry=None;last=None
    for q in ticks:
        if not isinstance(q,dict):raise ValueError("Invalid quote")
        t=q.get("time_msc");bid=q.get("bid");ask=q.get("ask")
        if type(t) not in (int,float) or not isfinite(t) or type(bid) not in (int,float) or type(ask) not in (int,float) or not all(isfinite(x) for x in (bid,ask)) or not 0<bid<=ask:
            raise ValueError("Invalid tick")
        if last is not None and t<last:raise ValueError("Unordered ticks")
        last=t
        if t<entry_after_msc:continue
        if entry is None:
            opening=(ask+slippage) if side=="BUY" else (bid-slippage)
            if opening<=0:raise ValueError("Unrepresentable entry")
            if (side=="BUY" and not (stop_price<opening<target_price)) or (side=="SELL" and not (target_price<opening<stop_price)):
                return dict(status="INVALID_STRUCTURE",execution_allowed=False)
            entry=dict(entry_at=t,entry_price=opening,entry_bid=bid,entry_ask=ask)
            # Evaluate stop/target on the opening quote as well.
        price=bid if side=="BUY" else ask
        stop_hit=price<=stop_price if side=="BUY" else price>=stop_price
        target_hit=price>=target_price if side=="BUY" else price<=target_price
        if stop_hit or target_hit:
            exit_price=market_exit_price(side=side,bid=bid,ask=ask,slippage=slippage)
            delta=(exit_price-entry["entry_price"]) if side=="BUY" else (entry["entry_price"]-exit_price)
            return dict(status="CLOSED",side=side,entry_at=entry["entry_at"],exit_at=t,
                entry_price=entry["entry_price"],exit_price=exit_price,
                exit_reason="STOP" if stop_hit else "TARGET",price_pnl_per_unit=delta,
                execution_allowed=False)
    if entry is None:return dict(status="NO_ENTRY_QUOTE",execution_allowed=False)
    mark=(ticks[-1]["bid"] if side=="BUY" else ticks[-1]["ask"])
    marked_pnl=(mark-entry["entry_price"]) if side=="BUY" else (entry["entry_price"]-mark)
    return dict(status="OPEN",side=side,entry_at=entry["entry_at"],entry_price=entry["entry_price"],
                last_mark=mark,marked_price_pnl_per_unit=marked_pnl,execution_allowed=False)
