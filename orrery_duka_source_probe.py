"""Fetch one Dukascopy XAUUSD hourly raw tick archive for source verification only.
No orders, credentials, fabricated fills, or broker-specific PnL.
"""
import argparse
import hashlib
import json
import lzma
import struct
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hour", default="2026-10-22T12:00:00+00:00")
    parser.add_argument("--symbol", choices=("XAUUSD", "USDJPY"), default="XAUUSD")
    parser.add_argument("--out", default="duka_source_sample")
    args = parser.parse_args()
    hour = datetime.fromisoformat(args.hour.replace("Z", "+00:00"))
    if hour.tzinfo is None or hour.utcoffset() != timedelta(0) or hour.minute or hour.second or hour.microsecond:
        raise ValueError("Whole-hour UTC timestamp required")
    if hour + timedelta(hours=1) >= datetime.now(timezone.utc):
        raise ValueError("Use a fully completed historical hour")
    out = Path(args.out)
    out.mkdir(exist_ok=False)
    url = (f"https://datafeed.dukascopy.com/datafeed/{args.symbol}/"
           f"{hour.year:04d}/{hour.month - 1:02d}/{hour.day:02d}/{hour.hour:02d}h_ticks.bi5")
    manifest = {"symbol": args.symbol, "hour_utc": hour.isoformat(), "source_url": url,
                "source": "Dukascopy public archive; not MetaQuotes-Demo",
                "execution_allowed": False, "backtest_complete": False}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ORRERY-FX-research/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read(30_000_001)
        if len(raw) > 30_000_000 or not raw:
            raise ValueError("Missing/oversized hourly data")
        decoded = lzma.decompress(raw)
        if not decoded or len(decoded) % 20:
            raise ValueError("Invalid Dukascopy 20-byte record framing")
        prior = -1
        spreads_nonnegative = 0
        for offset in range(0, len(decoded), 20):
            milliseconds, ask_raw, bid_raw, ask_volume, bid_volume = struct.unpack_from(">IIIff", decoded, offset)
            if not 0 <= milliseconds < 3_600_000 or milliseconds < prior:
                raise ValueError("Invalid/out-of-order timestamps")
            if not (ask_raw >= bid_raw > 0):
                raise ValueError("Nonpositive or inverted prices")
            from math import isfinite
            if not (isfinite(ask_volume) and isfinite(bid_volume) and ask_volume >= 0 and bid_volume >= 0):
                raise ValueError("Nonfinite/negative volumes")
            prior = milliseconds
            spreads_nonnegative += 1
        (out / "source.bi5").write_bytes(raw)
        manifest.update(status="RAW_TICKS_VALIDATED", raw_sha256=hashlib.sha256(raw).hexdigest(),
                        decoded_sha256=hashlib.sha256(decoded).hexdigest(), tick_count=spreads_nonnegative,
                        note="Price scale and broker contract/cost terms NOT calibrated; no USD profit calculated.")
    except (ValueError, lzma.LZMAError, urllib.error.URLError, TimeoutError, OSError) as exc:
        manifest.update(status="BLOCKED_SOURCE_FETCH", error_type=type(exc).__name__)
        if isinstance(exc, urllib.error.HTTPError):
            manifest["http_status"] = exc.code
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest))
    return 0 if manifest["status"] == "RAW_TICKS_VALIDATED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
