"""Convert verified closed-candle research observations to a UI-safe overlay payload.
No live feeds, forecasting, or order instructions; caller supplies provenance.
"""
from math import isfinite
from lsr02_level_observer import observe
from lsr02_structure import detect

def overlay(bars, *, symbol, interval, as_of, tenkan, kijun, span_b, shift,
            source, source_verified):
    if symbol not in ("XAUUSD","USDJPY") or interval not in (300,900,14400):
        raise ValueError("Unsupported symbol/timeframe")
    if source not in ("SYNTHETIC_TEST","VERIFIED_DEMO_CLOSED_BARS") or type(source_verified) is not bool:
        raise ValueError("Missing provenance")
    if source=="VERIFIED_DEMO_CLOSED_BARS" and not source_verified:
        raise ValueError("No verified DEMO provenance")
    if not isinstance(bars,list) or not 2<=len(bars)<=100:
        raise ValueError("Invalid candle count")
    detect(bars,as_of=as_of,interval=interval)
    if as_of-bars[-1]["close_time"]>=interval:
        raise ValueError("Stale bars")
    o=observe(bars,as_of=as_of,interval=interval,
              tenkan=tenkan,kijun=kijun,span_b=span_b,shift=shift)
    return dict(schema="ORRERY_OVERLAY_V1",source=source,
        source_verified=source_verified,symbol=symbol,interval_seconds=interval,
        as_of=as_of,latest_closed_at=bars[-1]["close_time"],
        bars=[{k:b[k] for k in ("open","high","low","close","close_time")} for b in bars],
        levels=o["levels"],reasons=o["reasons"],cloud_location=o["cloud_location"],
        status="WAIT",execution_allowed=False,
        disclaimer="Research annotations only; not predictive prices or orders.")
