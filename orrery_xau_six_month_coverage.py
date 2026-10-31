"""Fail-closed coverage assessment for a requested six-month XAUUSD backtest.
Dataset timestamps and candidate trades are NOT interchangeable.
"""
import csv,datetime as dt,json
from pathlib import Path
UTC=dt.timezone.utc
START=dt.datetime(2026,4,28,tzinfo=UTC)
END=dt.datetime(2026,10,28,tzinfo=UTC)
def run():
    p=Path("public_xau_bars/XAUUSD_M1_UNVERIFIED_QUOTE.csv")
    with p.open(newline="",encoding="utf-8") as f:
        reader=csv.DictReader(f)
        first=last=None;count=0;inside=0
        for r in reader:
            t=dt.datetime.fromisoformat(r["timestamp_utc"])
            if first is None:first=t
            last=t;count+=1
            if START<=t<END:inside+=1
    data={"requested_start_utc":START.isoformat(),"requested_end_utc_exclusive":END.isoformat(),
          "available_first_utc":first.isoformat() if first else None,
          "available_last_utc":last.isoformat() if last else None,
          "total_m1_rows":count,"rows_inside_requested_window":inside,
          "six_month_backtest_complete":bool(first and last and first<=START and last>=END-dt.timedelta(minutes=1)),
          "market_session_verified":False,"broker_execution_verified":False,
          "six_month_net_usd":None,"six_month_win_rate_pct":None,
          "note":"Session gaps require a separate audited trading calendar; date coverage alone never establishes backtest completeness."}
    Path("public_xau_six_month_coverage.json").write_text(json.dumps(data,indent=2)+"\n")
    print(json.dumps(data))
if __name__=="__main__":run()
