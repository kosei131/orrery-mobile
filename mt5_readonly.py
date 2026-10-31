"""ORRERY FX v5 - local MT5 read-only diagnostic.
Run on Windows with MT5 already logged in. Never uploads or stores account data.
"""
from datetime import datetime, timedelta, timezone
import json
import sys
import argparse
from pathlib import Path

try:
    import MetaTrader5 as mt5
except ImportError:
    print("Missing MetaTrader5. Run: py -m pip install MetaTrader5")
    sys.exit(2)

def safe_float(value):
    return round(float(value), 5)

def main():
    parser = argparse.ArgumentParser(description="ORRERY MT5 read-only demo diagnostic")
    parser.add_argument("--export", action="store_true", help="Write private JSON snapshot to Downloads")
    args = parser.parse_args()
    if not mt5.initialize():
        print("MT5 connection failed.")
        print("Open Windows MetaTrader 5 and log in to your DEMO account first.")
        return 1
    try:
        a = mt5.account_info()
        if a is None:
            print("Cannot read account.")
            return 1
        if a.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
            print("SAFETY STOP: This diagnostic accepts DEMO accounts only.")
            return 2
        positions = mt5.positions_get()
        if positions is None:
            print("Could not read positions.")
            return 1
        end = datetime.now(timezone.utc)
        deals = mt5.history_deals_get(end - timedelta(days=7), end)
        if deals is None:
            print("Could not read last 7 days of deals.")
            return 1
        report = {
            "status": "READ_ONLY_DEMO",
            "broker_server": a.server,
            "account_last4": str(a.login)[-4:],
            "currency": a.currency,
            "balance": safe_float(a.balance),
            "equity": safe_float(a.equity),
            "margin_free": safe_float(a.margin_free),
            "positions": [
                {"symbol": p.symbol, "side": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                 "lots": safe_float(p.volume), "open_price": safe_float(p.price_open),
                 "current_price": safe_float(p.price_current), "pnl": safe_float(p.profit)}
                for p in positions
            ],
            "history_7d_count": len(deals),
            "checked_at_utc": end.isoformat()
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if args.export:
            target = Path.home() / "Downloads" / "orrery-mt5-snapshot.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Local private snapshot saved: {target}")
        print("\nNo orders sent. No credentials saved. No data uploaded.")
        return 0
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    sys.exit(main())
