# SPDX-License-Identifier: GPL-3.0-only
"""Pinned candidate spread stress and causal one-position availability review."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import gzip,json
from pathlib import Path
from orrery_paired_archive_study import read_side,SOURCE_PINS,evaluate_plan,summary
from orrery_halftrend_patterns import sequence
from orrery_entry_stability_cost import stats

ROOT=Path(__file__).resolve().parent
STEM=ROOT/'research_evidence/local-history-20261101/halftrend_patterns_20261102'
MANIFEST_SHA256='f992759563e110ef2ed42dc3352f71963e1f0612d35e8c3fbb4b7b7746c2d982'
DELTAS=(0.,.3,.6)
PREENTRY={'UNKNOWN_ANCHOR_SIDE_HISTORY','UNKNOWN_ENTRY_HISTORY','UNKNOWN_PRE_ENTRY_HISTORY',
          'STRUCTURE_BREACHED_BEFORE_ENTRY','STOP_INVALID_AT_ENTRY'}
POSITION={'RESOLVED_REFERENCE','CENSORED_AT_SIDE_GAP','AMBIGUOUS_SAME_MINUTE'}


def one_position(rows):
    ids=set()
    for r in rows:
        if r.get('status') not in PREENTRY|POSITION or type(r.get('entry_at')) is not int:
            raise ValueError('Known status and explicit entry clock required')
        cid=r.get('candidate_id')
        if not isinstance(cid,str) or not cid or cid in ids:raise ValueError('Unique candidate ID required')
        ids.add(cid)
        if r['status']=='RESOLVED_REFERENCE':
            if type(r.get('exit_at')) is not int or r['exit_at']<r['entry_at']:raise ValueError('Causal exit clock required')
            if r.get('exit_reason') not in ('TP_TOUCH','SL_TOUCH','STOP_AT_OBSERVED_OPEN','TIMEOUT_CLOSE'):
                raise ValueError('Supported price exit reason required')
        if r['status']=='AMBIGUOUS_SAME_MINUTE' and (type(r.get('exit_at')) is not int or r['exit_at']<r['entry_at']):
            raise ValueError('Ambiguous exit minute required')
        if r['status']=='CENSORED_AT_SIDE_GAP' and (type(r.get('last_observed_until')) is not int or r['last_observed_until']<r['entry_at']):
            raise ValueError('Observed gap clock required')
    accepted=[];decisions=[];busy_until=-1;unknown_from=None
    for r in sorted(rows,key=lambda r:(r['entry_at'],r['candidate_id'])):
        t=r['entry_at'];status=r['status']
        if busy_until is None:
            decision='BLOCK_UNKNOWN_POSITION' if t>=unknown_from else 'BLOCK_BUSY'
        elif t<=busy_until:decision='BLOCK_BUSY_OR_SAME_CLOCK'
        elif status in PREENTRY:decision='REJECT_PREENTRY_'+status
        else:
            decision='ACCEPT_MODEL_ENTRY';accepted.append(r)
            if status=='CENSORED_AT_SIDE_GAP':
                busy_until=None;unknown_from=r['last_observed_until']+60
            elif status=='AMBIGUOUS_SAME_MINUTE':busy_until=r['exit_at']+60
            else:
                busy_until=r['exit_at']+(60 if r['exit_reason'] in ('TP_TOUCH','SL_TOUCH') else 0)
        decisions.append(dict(candidate_id=r['candidate_id'],entry_at=t,decision=decision))
    return dict(accepted_candidate_ids=[r['candidate_id'] for r in accepted],
        accepted_position_summary=summary(accepted),decision_counts=dict(Counter(r['decision'] for r in decisions)),
        decisions=decisions,ended_with_unknown_position=busy_until is None,
        all_position_reference_sequence=sequence(accepted),
        resolved_only_reference_sequence=sequence(accepted,True),account_return_pct=None)


def concentration(rows):
    closed=[r for r in rows if r['status']=='RESOLVED_REFERENCE'];weeks={}
    for r in closed:
        iso=datetime.fromtimestamp(r['entry_at'],timezone.utc).isocalendar()
        weeks.setdefault(f'{iso.year}-W{iso.week:02d}',[]).append(r)
    winners=sorted((i for i,r in enumerate(closed) if r['r']>0),key=lambda i:(-closed[i]['r'],closed[i]['entry_at'],closed[i]['candidate_id']))
    best=max(sorted(weeks),key=lambda w:sum(r['r'] for r in weeks[w])) if weeks else None
    return dict(resolved_only=stats(closed),weekly={w:stats(v) for w,v in sorted(weeks.items())},
        remove_top_positive_trades={str(n):dict(removed=min(n,len(winners)),remaining=stats([r for i,r in enumerate(closed) if i not in set(winners[:n])])) for n in (1,2,3)},
        best_week=best,excluding_best_week=stats([r for w,rs in weeks.items() if w!=best for r in rs]),
        descriptive_only=True,unknown_outcomes_imputed=False)


def load_parent():
    raw=Path(str(STEM)+'_manifest.json').read_bytes()
    if sha256(raw).hexdigest()!=MANIFEST_SHA256:raise ValueError('Parent manifest changed')
    m=json.loads(raw);zipped=Path(str(STEM)+'.json.gz').read_bytes()
    if sha256(zipped).hexdigest()!=m['gzip_sha256']:raise ValueError('Parent archive changed')
    raw=gzip.decompress(zipped)
    if sha256(raw).hexdigest()!=m['uncompressed_sha256']:raise ValueError('Parent evidence changed')
    for name,pin in m['engine_code_sha256'].items():
        if sha256((ROOT/name).read_bytes()).hexdigest()!=pin:raise ValueError('Original engine changed')
    return json.loads(raw)


def run(folder,output):
    parent=load_parent();folder=Path(folder);base_bid={};base_ask={}
    for name,pin in SOURCE_PINS.items():
        rows,audit=read_side(folder/name)
        if audit['sha256']!=pin:raise ValueError('Source changed')
        dest=base_bid if name.startswith('bid_') else base_ask
        if set(rows)&set(dest):raise ValueError('Duplicate source clock')
        dest.update(rows)
    if set(base_bid)!=set(base_ask):raise ValueError('Exact paired coverage required')
    candidates={c['id']:c for c in parent['candidates']};results={};baseline_matches=0
    for delta in DELTAS:
        half=delta/2
        bid={t:{k:v-half for k,v in b.items()} for t,b in base_bid.items()}
        ask={t:{k:v+half for k,v in b.items()} for t,b in base_ask.items()}
        for window,w in parent['results'].items():
            for model,baseline in w['models'].items():
                rows=[]
                for prior in baseline['outcomes']:
                    c=candidates[prior['candidate_id']];stop=known=None
                    if model.endswith('ANCHOR_EXTREME'):
                        times=range(c['anchor_open'],c['anchor_known_at'],60)
                        if any(t not in base_bid or t not in base_ask for t in times):
                            rows.append(dict(entry_at=c['entry_at'],side=c['side'],status='UNKNOWN_ANCHOR_SIDE_HISTORY',candidate_id=c['id']));continue
                        stop=c['anchor_bid_low'] if c['side']=='BUY' else max(base_ask[t]['high'] for t in times)
                        known=c['anchor_known_at']
                    r=evaluate_plan(dict(first_poi_touch_close=c['entry_at'],side=c['side']),bid,ask,
                                    structural_stop=stop,structural_known_at=known)
                    rows.append(dict(r,candidate_id=c['id']))
                if delta==0:
                    if rows!=baseline['outcomes']:raise ValueError('Baseline individual outcomes changed')
                    baseline_matches+=1
                results.setdefault(window,{}).setdefault(model,{})[str(delta)]=dict(
                    extra_spread_price_units=delta,all_candidate_summary=summary(rows),outcomes=rows,
                    one_position=one_position(rows),concentration_resolved_only=concentration(rows))
    report=dict(status='HALFTREND_PATTERN_SPREAD_AND_SINGLE_POSITION_REVIEW',models=results,
        parent_manifest_sha256=MANIFEST_SHA256,source_pins=SOURCE_PINS,
        baseline_twelve_models_exact_match=baseline_matches==12,scenario_count=36,
        extra_spread_price_units=DELTAS,code_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        execution_allowed=False,adopted=False,out_of_sample=False,formal_lsr02=False,wt_x_reproduced=False,
        net_expectancy_r=None,account_return_pct=None,account_max_dd_usd=None,
        limitations=['Same inspected periods and candidates; not independent OOS.',
            'Widened execution quotes only, frozen baseline signals and structural anchor levels.',
            'Unresolved post-entry gap blocks subsequent entries through the end of that research window.',
            'Dual-touch OCO is assumed closed by minute end, while profit remains unknown.',
            'One-position policy alone does not replay daily loss/losing streak, margin or account controls.',
            'Fees, extra slippage and swap unknown; no actual profit or account return.',
            'Winner/week removal is descriptive sensitivity, not an executable selection rule.'])
    with Path(output).open('x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({w:{m:{d:dict(all=v['all_candidate_summary'],single=v['one_position']['accepted_position_summary'],single_decisions=v['one_position']['decision_counts']) for d,v in ds.items()} for m,ds in ms.items()} for w,ms in results.items()}))
    return report

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.folder,a.output)
