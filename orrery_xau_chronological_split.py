"""Chronological exploratory split, using fixed VHF threshold 0.50.
No random train/test mixing; no claim of independent validation because
threshold was chosen after reviewing the full sample.
"""
import datetime as dt,json
from pathlib import Path
from orrery_xau_confidence_research import evaluate

def run():
    data=evaluate(Path("public_xau_hypothetical_pnl.json"),Path("public_xau_sequence_report.json"))
    cut=int(dt.datetime(2026,7,1,tzinfo=dt.timezone.utc).timestamp())
    groups={}
    for label,rows in (("before_2026_07_01",[x for x in data["details"] if x["touch_close_utc"]<cut]),
                       ("from_2026_07_01",[x for x in data["details"] if x["touch_close_utc"]>=cut])):
        groups[label]={}
        for tier in ("higher_vhf","lower_vhf"):
            trades=[x for x in rows if x["tier"]==tier]
            count=len(trades);wins=sum(x["r"]>0 for x in trades)
            groups[label][tier]={"count":count,"wins":wins,
                "win_rate_pct":round(100*wins/count,2) if count else None,
                "mean_r":round(sum(x["r"] for x in trades)/count,4) if count else None}
    out={"method":"chronological descriptive split, NOT independently out-of-sample",
         "split_utc":"2026-07-01T00:00:00Z","groups":groups,
         "high_lot_enabled":False,
         "warning":"VHF 0.50 threshold was inspected on complete data, so both halves are contaminated for validation; use independent unseen observations before enabling lot scaling."}
    Path("public_xau_chronological_split.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps(out))
if __name__=="__main__":run()
