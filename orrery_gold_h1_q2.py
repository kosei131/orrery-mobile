# SPDX-License-Identifier: GPL-3.0-only
"""Unchanged H1 rising-VHF hypothesis on separately evaluated 2025 Q2."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from orrery_gold_ab_archive_comparison import aggregate_complete
from orrery_gold_clock_audit import audit as clock_audit
from orrery_gold_entry_routing import START, END, load as load_q2
from orrery_gold_h1_state import EVIDENCE, describe
from orrery_gold_h1_vhf_rising import replay_rising
from orrery_gold_session_hourly import replay, signals


def compare(bid, ask, m5, start=START, end=END):
    if (start, end) != (START, END):
        raise ValueError('Fixed Q2 study boundaries required')
    h1=aggregate_complete(m5,3600)
    raw=list(signals(h1,end,session=True))
    baseline,base_skips=replay(raw,bid,ask,end)
    rising,counts=replay_rising(h1,bid,ask,end)
    if counts['raw_signals']!=len(raw):
        raise ValueError('Candidate universes disagree')
    old_clocks={r['at_utc'] for r in baseline}
    arms={}
    for name,rows,skips in (('BASELINE',baseline,base_skips),('VHF_RISING',rising,counts['skipped'])):
        arms[name]=dict(describe(rows),skipped=skips,
            resolved_per_calendar_week=sum(r['status']=='RESOLVED_REFERENCE' for r in rows)*604800/(end-start),
            by_utc_month={f'2025-{m:02}':describe([r for r in rows if
                datetime.fromtimestamp(r['at_utc'],timezone.utc).month==m]) for m in (4,5,6)})
    return dict(start_utc=datetime.fromtimestamp(start,timezone.utc).isoformat(),
        end_utc_exclusive=datetime.fromtimestamp(end,timezone.utc).isoformat(),
        complete_h1=len(h1),raw_signals=len(raw),passing_signals=counts['passing_signals'],
        excluded_by_vhf=counts['excluded_by_vhf'],
        entries_absent_from_baseline=sum(r['at_utc'] not in old_clocks for r in rising),
        arms=arms,records=dict(BASELINE=baseline,VHF_RISING=rising))


def run(root):
    raw=(EVIDENCE/'gold_h1_q2_plan.json').read_bytes()
    plan=json.loads(raw)
    for filename,expected in plan['files_sha256'].items():
        if sha256(Path(__file__).parent.joinpath(filename).read_bytes()).hexdigest()!=expected:
            raise ValueError('Q2 study code/input pin mismatch: '+filename)
    bid,ask,m5,audit=load_q2(root)
    return dict(study='gold_h1_vhf_q2_v1',source_revision=plan['source_revision'],
        audit=audit,clock_audit=clock_audit(bid,ask,START,END),**compare(bid,ask,m5),
        plan_sha256=sha256(raw).hexdigest(),hypotheses_replayed=1,
        new_period_for_h1_hypothesis=True,archive_previously_used_for_other_strategies=True,
        independent_holdout_verified=False,out_of_sample=False,
        historical_session_rule_authenticated=False,historical_holiday_exceptions_authenticated=False,
        account_return_pct=None,account_max_dd_pct=None,adoption_allowed=False,execution_allowed=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_2025_q2',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    result=run(args.archive_2025_q2)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(result,stream,indent=2,allow_nan=False)
        stream.write('\n')
