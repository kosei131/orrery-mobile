"""Separate recurring H4 market-closure candidate gaps from unexplained gaps.
Research only: pattern inference is not official broker calendar verification.
"""
from collections import Counter
from orrery_public_xau_h4_gap_diagnostic import audit

def evaluate(path):
    report=audit(path)
    patterns=Counter()
    for item in report["example_gaps"]:
        patterns[(item["after_open_utc"][11:16],item["before_open_utc"][11:16],item["missing_h4_grid_bars"])]+=1
    likely=next((p for p in report["top_gap_patterns"] if p["from_utc"]=="16:00"
                 and p["to_utc"]=="00:00" and p["missing_h4_bars"]==1),None)
    return {"total_h4_gaps":report["gap_count"],
            "recurring_daily_closure_candidate_count":likely["count"] if likely else 0,
            "unexplained_or_non_daily_gaps":report["gap_count"]-(likely["count"] if likely else 0),
            "allow_bar_sequence_bridge":False,
            "calendar_or_feed_session_verified":False,
            "note":"Do not synthesize H4 candles across closures or use absent bars in swing-pivot calculations."}
