"""Audit why an existing research funnel generates too few signals.
No parameter optimization and no claim that more signals imply more profit.
"""
import json
from pathlib import Path

def run():
    s=json.loads(Path("public_xau_sequence_report.json").read_text())
    p=json.loads(Path("public_xau_five_month_study.json").read_text())
    stages=[
        ("M15 sweeps (full public sample)",s["m15_sweeps"]),
        ("Opposite M5 BOS/CHoCH paired (full sample)",s["unique_one_to_one_sweep_m5_matches"]),
        ("VHF .4 rising (full sample)",s["sweep_time_vhf_research_passed"]),
        ("POI retouched (full sample)",s["vhf_passed_with_postconfirmation_poi_touch"]),
        ("Five-month simulated candidates",p["all_matched_poi_research"]["count"]),
        ("Five-month VHF >=.5 candidates",p["vhf_at_least_050_research"]["count"])
    ]
    out={"status":"DIAGNOSTIC_ONLY_NOT_OPTIMIZATION",
         "stages":[{"stage":name,"count":count} for name,count in stages],
         "stage_transition_warning":"First four stages use all available sample; last two use five-month window. Do not divide across windows.",
         "key_bottleneck":"640 sweeps become 132 paired structures, then 30 VHF filtered, then 14 POI touches; 2 high VHF in five-month sample",
         "profit_target_usd_per_week":5000,
         "capital_examples_at_weekly_return_pct":[{"weekly_return_pct":r,"capital_needed_usd":round(5000/(r/100))} for r in (1,2,5)],
         "trade_count_is_not_expectancy":True,"high_lot_enabled":False}
    Path("public_xau_funnel_bottleneck.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps(out))
if __name__=="__main__":run()
