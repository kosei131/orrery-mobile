"""Interactive Windows launcher for the existing read-only DEMO historical pilot.

No orders, credentials, network uploads, or invented trading costs.
Run from the checked-out fix/fx-safety-verification repository on Windows.
"""
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def ask(label, default=None):
    suffix = f" [{default}]" if default is not None else ""
    answer = input(f"{label}{suffix}: ").strip()
    return answer or default


def utc_time(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0) or dt.microsecond:
        raise ValueError("Use whole-second UTC timestamps with +00:00 or Z")
    return dt.astimezone(timezone.utc)


def main():
    root = Path(__file__).resolve().parent
    template_path = root / "pilot_settings.example.json"
    pilot_path = root / "lsr03_mt5_pilot.py"
    if not template_path.is_file() or not pilot_path.is_file():
        raise RuntimeError("Required pilot source/template not found in this folder")
    try:
        import MetaTrader5  # noqa: F401 -- only checks dependency; never logs in
    except ImportError as exc:
        raise RuntimeError("MetaTrader5 Python package unavailable. Install it on Windows first.") from exc

    cfg = json.loads(template_path.read_text(encoding="utf-8"))
    print("ORRERY FX real-data pilot: DEMO-only, read-only, <=24h.")
    print("Do NOT enter account passwords, login IDs, or other secrets.")
    terminal = ask("MT5 terminal64.exe absolute path", r"C:\Program Files\MetaTrader 5\terminal64.exe")
    if not Path(terminal).is_file():
        raise ValueError("MT5 terminal not found at the supplied path")
    cfg["symbol"] = ask("Symbol", "XAUUSD")
    if cfg["symbol"] not in ("XAUUSD", "USDJPY"):
        raise ValueError("Only exact XAUUSD or USDJPY is supported")
    cfg["source"] = ask("Non-sensitive source label", "MetaQuotes-Demo-research")
    print("Enter an already completed continuous market session. All timestamps are UTC.")
    cfg["h4_start_utc"] = ask("H4 warmup start UTC (ISO 8601)")
    cfg["structure_start_utc"] = ask("Structure start UTC (ISO 8601)")
    cfg["tick_start_utc"] = ask("Tick start UTC (ISO 8601)")
    cfg["end_utc"] = ask("Tick end UTC (ISO 8601)")
    h, s, t, e = [utc_time(cfg[k]) for k in (
        "h4_start_utc", "structure_start_utc", "tick_start_utc", "end_utc")]
    if not h <= s <= t < e < datetime.now(timezone.utc):
        raise ValueError("Time ordering must be H4 <= structure <= tick < end < now")
    if e - t > timedelta(hours=24) or e - h > timedelta(days=14):
        raise ValueError("Pilot supports max 24h ticks and 14d warmup")
    cfg["round_trip_cost_per_unit"] = float(ask(
        "Documented estimated round-trip cost in quote-price units per underlying unit (not USD/lot)"))
    cfg["slippage"] = float(ask(
        "Documented slippage assumption in quote-price units per underlying unit"))
    cfg["cost_assumption_source"] = ask(
        "Cost and slippage assumptions source (label; no secrets)")
    if not cfg["cost_assumption_source"] or not cfg["source"]:
        raise ValueError("Nonempty source labels are required")
    import lsr03_mt5_pilot
    lsr03_mt5_pilot._config(cfg, datetime.now(timezone.utc))
    print("WARNING: These are assumptions, NOT verified historical broker costs.")
    folder_name = ask("New unique output directory name", "orrery_pilot_real_001")
    out = (root / folder_name).resolve()
    if out == root or root not in out.parents or out.exists() or Path(folder_name).name != folder_name:
        raise ValueError("Output must be a new path inside this repository")
    config_path = root / f"{folder_name}.settings.local.json"
    if config_path.exists():
        raise ValueError("This run settings file already exists; choose a new output name")
    config_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(f"Config saved to {config_path.name}; preserve it with the resulting report.")
    print("Starting historical read-only pilot. No demo or live trades are placed.")
    command = [sys.executable, str(pilot_path), "--config", str(config_path),
               "--output", str(out), "--terminal-path", terminal]
    return subprocess.call(command, cwd=root)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, EOFError) as exc:
        print(f"STOPPED: {exc}", file=sys.stderr)
        sys.exit(1)
