"""Read-only conversion of a fresh MT5 DEMO dashboard snapshot into chart overlays.

This is structural validation of a caller-provided snapshot, NOT cryptographic
authentication or a direct broker connection. No orders, no network, no storage.
"""
from datetime import datetime
from lsr02_overlay_export import overlay
from lsr02_sequence import number

FRAMES={"5m":300,"15m":900,"4H":14400}

def export_snapshot(snapshot, *, symbol, timeframe, now,
                    tenkan=9,kijun=26,span_b=52,shift=26):
    if symbol not in ("XAUUSD","USDJPY") or timeframe not in FRAMES or not number(now):
        raise ValueError("Unsupported research request")
    if not isinstance(snapshot,dict) or snapshot.get("status")!="READ_ONLY_DEMO":
        raise ValueError("Only MT5 DEMO snapshot format is permitted")
    checked=datetime.fromisoformat(snapshot["checked_at_utc"])
    if checked.utcoffset() is None or checked.utcoffset().total_seconds()!=0:
        raise ValueError("UTC snapshot timestamp required")
    if not 0<=now-checked.timestamp()<=5:
        raise ValueError("Stale or future DEMO snapshot")
    matches=[c for c in snapshot["charts"] if isinstance(c,dict)
             and c.get("symbol")==symbol and c.get("timeframe")==timeframe]
    if len(matches)!=1 or matches[0].get("status")!="CLOSED_BARS_AVAILABLE":
        raise ValueError("Unique closed-candle chart required")
    raw=matches[0]["bars"]; interval=FRAMES[timeframe]
    if not isinstance(raw,list) or not 2<=len(raw)<=100:
        raise ValueError("Unsupported closed-candle count")
    bars=[]
    for item in raw:
        timestamp=item["time"]
        if not number(timestamp) or timestamp%interval:
            raise ValueError("Unaligned candle timestamp")
        bars.append(dict(close_time=timestamp+interval,
                         **{k:item[k] for k in ("open","high","low","close")}))
    result=overlay(bars,symbol=symbol,interval=interval,as_of=now,
                   tenkan=tenkan,kijun=kijun,span_b=span_b,shift=shift,
                   source="VERIFIED_DEMO_CLOSED_BARS",source_verified=True)
    result["provenance_note"]="Format and recency checked; dashboard origin not authenticated"
    return result
