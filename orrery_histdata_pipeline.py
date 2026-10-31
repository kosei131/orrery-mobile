#!/usr/bin/env python3
"""Offline one-command HistData ZIP to validated multitimeframe candles.
No network, no trading, no backfill of missing minutes.
"""
import argparse
import json
from pathlib import Path
from orrery_histdata_m1_import import convert
from orrery_m1_complete_bars import aggregate

def pipeline(source: Path, symbol: str, dest: Path) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    m1 = dest / f"{symbol}_M1_UTC.csv"
    report = {"import": convert(source, m1, symbol), "timeframes": {}}
    for timeframe in ("M5", "M15", "H4"):
        report["timeframes"][timeframe] = aggregate(
            m1, dest / f"{symbol}_{timeframe}_UTC.csv", timeframe)
    report["ready_for_strategy_replay"] = (
        report["timeframes"]["H4"]["complete_bars"] >= 50
        and report["timeframes"]["M15"]["complete_bars"] >= 100
        and report["timeframes"]["M5"]["complete_bars"] >= 200
    )
    report["ready_is_only_a_data_volume_gate"] = True
    report["broker_execution_calibrated"] = False
    report["verified_profit_usd"] = None
    (dest / "pipeline_manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("histdata_zip", type=Path)
    p.add_argument("--symbol", required=True, choices=("XAUUSD", "USDJPY"))
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    print(json.dumps(pipeline(args.histdata_zip, args.symbol, args.out), indent=2))
