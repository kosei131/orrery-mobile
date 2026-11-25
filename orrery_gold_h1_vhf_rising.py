# SPDX-License-Identifier: GPL-3.0-only
"""One post-diagnostic hypothesis: rising VHF14, full occupation replay."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from orrery_gold_ab_archive_comparison import aggregate_complete
from orrery_gold_h1_state import EVIDENCE, describe, features
from orrery_gold_nested_wave_october import complete_m5
from orrery_gold_pullback_study import START, END, load_archive
from orrery_gold_session_breakout import Q4_START, load_q4
from orrery_gold_session_hourly import chains, measure, replay, signals


def replay_rising(h1, bid, ask, end):
    raw=list(signals(h1,end,session=True))
    by_clock={r['at_utc']:r for r in raw}
    selected=[]
    for window in chains(h1,session=True):
        at=window[-1]['close_time']
        if at not in by_clock:
            continue
        signal=by_clock[at]
        f=features(window,signal,bid[at]['open'] if at in bid else None,
                   ask[at]['open'] if at in ask else None)
        if f['vhf14_slope']=='RISING':
            selected.append(signal)
    rows,skips=replay(selected,bid,ask,end)
    return rows,dict(raw_signals=len(raw),passing_signals=len(selected),
                     excluded_by_vhf=len(raw)-len(selected),skipped=skips)


def period(bid,ask,m5,start,end,expected):
    if measure(bid,ask,m5,start,end)!=expected:
        raise ValueError('Unchanged baseline did not reproduce')
    rows,counts=replay_rising(aggregate_complete(m5,3600),bid,ask,end)
    baseline=expected['records']['SESSION_HYPOTHESIS']
    old_clocks={r['at_utc'] for r in baseline}
    months=sorted({datetime.fromtimestamp(t,timezone.utc).strftime('%Y-%m') for t in range(start,end,86400)})
    return dict(baseline_reproduced=True,baseline=describe(baseline),rising=describe(rows),
        start_utc=expected['start_utc'],end_utc_exclusive=expected['end_utc_exclusive'],
        **counts, entries_absent_from_baseline=sum(r['at_utc'] not in old_clocks for r in rows),
        by_utc_month={m:describe([r for r in rows if datetime.fromtimestamp(r['at_utc'],timezone.utc).strftime('%Y-%m')==m]) for m in months},
        records=rows)


def run(root,prior_root):
    raw=(EVIDENCE/'gold_h1_vhf_rising_plan.json').read_bytes()
    plan=json.loads(raw)
    for filename,expected in plan['files_sha256'].items():
        if sha256(Path(__file__).parent.joinpath(filename).read_bytes()).hexdigest()!=expected:
            raise ValueError('Rising replay pin mismatch: '+filename)
    original=(EVIDENCE/'gold_session_hourly_results.json').read_bytes()
    baseline=json.loads(original)
    bid,ask,m5,_,_,_=load_archive(root)
    recent=period(bid,ask,m5,START,END,baseline['historical_2026'])
    bid,ask,_,_=load_q4(prior_root)
    m5=complete_m5({t:bid[t] for t in bid.keys() & ask.keys()},Q4_START,START)
    older=period(bid,ask,m5,Q4_START,START,baseline['separate_2025_q4'])
    return dict(study='gold_h1_vhf_rising_v1',hypotheses_replayed=1,
        historical_2026=recent,separate_2025_q4=older,baseline_sha256=sha256(original).hexdigest(),
        plan_sha256=sha256(raw).hexdigest(),hypothesis_selected_after_diagnostic=True,
        out_of_sample=False,historical_session_rule_authenticated=False,
        account_return_pct=None,account_max_dd_pct=None,execution_allowed=False,adoption_allowed=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_2026',type=Path)
    parser.add_argument('archive_2025_q4',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    result=run(args.archive_2026,args.archive_2025_q4)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(result,stream,indent=2,allow_nan=False)
        stream.write('\n')
