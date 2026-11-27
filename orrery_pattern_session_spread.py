# SPDX-License-Identifier: GPL-3.0-only
"""Frozen HalfTrend candidates: conditional weekly closures plus quote widening."""
from collections import Counter
import gzip,json
from hashlib import sha256
from math import isfinite
from pathlib import Path
from orrery_paired_archive_study import SOURCE_PINS, read_side, summary
from orrery_pattern_robustness import load_parent, one_position, MANIFEST_SHA256
from orrery_pattern_session_review import closure_scenario, audit_gaps

ROOT=Path(__file__).resolve().parent
SESSION_STEM=ROOT/'research_evidence/local-history-20261101/pattern_session_review_20261103'
SESSION_MANIFEST_SHA='8489cd68ae6e196ccbed671dcf5cef2e9dd7114304bb09c9ac8c89d81ddedd6a'
DELTAS=(0.,.3,.6)
SPEC={
    'extra_spread_price_units':DELTAS,
    'widening':'Bid OHLC minus delta/2, Ask OHLC plus delta/2, without modifying source files.',
    'signals':'Original frozen candidates and clocks; no indicator regeneration.',
    'fixed_stop':'6 price units from each stressed entry, TP at 1.5R.',
    'structural_stop':'Original Bid BUY anchor low or original Ask SELL anchor high; fixed across scenarios.',
    'structural_preentry':'Test original fixed level against widened execution quotes, with original known_at.',
    'session':'Reuse prior unauthenticated weekly-clock scenario, including deferred reopening timeout.',
    'holding':'120 wall-clock minutes; actual holding can extend through closure.',
    'positions':'All candidates plus separately replayed causal one-position availability, flat at each window start.',
    'selection':'No outcome-based candidate selection or parameter optimization.',
    'unknowns':'Unexplained gaps and ambiguous outcomes stay unknown; no zero imputation.',
    'other_costs':'Fees, swaps, further slippage, margin and account risk stops remain unknown.',
    'out_of_sample':False,
}
ENGINE_FILES=('orrery_pattern_session_spread.py','orrery_pattern_session_review.py',
              'orrery_pattern_robustness.py','orrery_paired_archive_study.py',
              'orrery_halftrend_patterns.py','lsr03_learning_rollup.py')


def load_session_parent():
    raw=Path(str(SESSION_STEM)+'_manifest.json').read_bytes()
    if sha256(raw).hexdigest()!=SESSION_MANIFEST_SHA:raise ValueError('Session manifest changed')
    m=json.loads(raw);z=Path(str(SESSION_STEM)+'.json.gz').read_bytes()
    if sha256(z).hexdigest()!=m['gzip_sha256']:raise ValueError('Session archive changed')
    raw=gzip.decompress(z)
    if sha256(raw).hexdigest()!=m['uncompressed_sha256']:raise ValueError('Session evidence changed')
    if sha256((ROOT/'orrery_pattern_session_review.py').read_bytes()).hexdigest()!=m['code_sha256']:
        raise ValueError('Session evaluator changed')
    return json.loads(raw)


def widen(bid,ask,delta):
    if type(delta) not in (float,int) or not isfinite(delta) or delta<0:
        raise ValueError('Finite nonnegative extra spread required')
    if not bid or set(bid)!=set(ask):raise ValueError('Exact paired coverage required')
    half=delta/2
    if any(b['low']<=half for b in bid.values()):raise ValueError('Nonpositive stressed Bid')
    return ({t:{k:v-half for k,v in b.items()} for t,b in bid.items()},
            {t:{k:v+half for k,v in b.items()} for t,b in ask.items()})


def outcomes(model,baseline,candidates,base_bid,base_ask,bid,ask,times):
    rows=[]
    for prior in baseline:
        c=candidates[prior['candidate_id']];stop=known=None
        if model.endswith('ANCHOR_EXTREME'):
            stamps=range(c['anchor_open'],c['anchor_known_at'],60)
            if any(t not in base_bid or t not in base_ask for t in stamps):
                rows.append(dict(entry_at=c['entry_at'],side=c['side'],status='UNKNOWN_ANCHOR_SIDE_HISTORY',candidate_id=c['id']))
                continue
            stop=c['anchor_bid_low'] if c['side']=='BUY' else max(base_ask[t]['high'] for t in stamps)
            known=c['anchor_known_at']
        r=closure_scenario(dict(first_poi_touch_close=c['entry_at'],side=c['side']),bid,ask,
                           structural_stop=stop,structural_known_at=known,paired_times=times)
        rows.append(dict(r,candidate_id=c['id']))
    return rows


def transitions(base,rows):
    if [r['candidate_id'] for r in base]!=[r['candidate_id'] for r in rows]:raise ValueError('Candidate order or IDs changed')
    return dict(Counter(a['status']+' -> '+b['status'] for a,b in zip(base,rows)))


def evaluate(parent,session,base_bid,base_ask):
    candidates={c['id']:c for c in parent['candidates']};times=sorted(base_bid)
    results={};baseline_rows={};matches=0
    for delta in DELTAS:
        bid,ask=widen(base_bid,base_ask,delta)
        for window,w in parent['results'].items():
            for model,baseline in w['models'].items():
                rows=outcomes(model,baseline['outcomes'],candidates,base_bid,base_ask,bid,ask,times)
                prior=session['results'][window][model]
                key=(window,model)
                if delta==0:
                    changes={x['strict']['candidate_id']:x['conditional'] for x in prior['changed_outcomes']}
                    expected=[changes.get(r['candidate_id'],r) for r in baseline['outcomes']]
                    if rows!=expected or summary(rows)!=prior['conditional']:
                        raise ValueError('Baseline session individual outcomes changed')
                    baseline_rows[key]=rows;matches+=1
                single=one_position(rows)
                if delta==0 and {k:v for k,v in single.items() if k!='decisions'}!=prior['conditional_single']:
                    raise ValueError('Baseline causal position availability changed')
                results.setdefault(window,{}).setdefault(model,{})[str(delta)]=dict(
                    extra_spread_price_units=delta,all_candidate_summary=summary(rows),outcomes=rows,
                    one_position=single,status_transitions_from_zero=transitions(baseline_rows[key],rows),
                    reference_holding_max_minutes=max(((r['exit_at']-r['entry_at'])//60 for r in rows if r['status']=='RESOLVED_REFERENCE'),default=None))
    return results,matches


def run(folder,stem):
    parent=load_parent();session=load_session_parent();bid={};ask={};receipts=[]
    for name,pin in SOURCE_PINS.items():
        data,receipt=read_side(Path(folder)/name)
        if receipt['sha256']!=pin:raise ValueError('Source pin mismatch')
        dest=bid if name.startswith('bid_') else ask
        if set(dest)&set(data):raise ValueError('Duplicate source clock')
        dest.update(data);receipts.append(dict(name=name,**receipt))
    audit=audit_gaps(bid,ask)
    if audit!=session['audit']:raise ValueError('Original paired gap audit changed')
    if any(ask[t][k]<bid[t][k] for t in bid for k in ('open','high','low','close')):raise ValueError('Crossed quote')
    results,matches=evaluate(parent,session,bid,ask)
    report=dict(status='CONDITIONAL_WEEKLY_SESSION_EXTRA_SPREAD_STRESS',specification=SPEC,
        specification_sha256=sha256(json.dumps(SPEC,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        session_manifest_sha256=SESSION_MANIFEST_SHA,parent_manifest_sha256=MANIFEST_SHA256,
        original_gap_audit=audit,source_files=receipts,results=results,scenario_count=36,
        baseline_twelve_individual_outcomes_and_position_policies_exact_match=matches==12,
        engine_code_sha256={n:sha256((ROOT/n).read_bytes()).hexdigest() for n in ENGINE_FILES},
        adopted=False,execution_allowed=False,independent_holdout=False,formal_lsr02=False,
        calendar_authenticated=False,source_authenticity_verified=False,
        net_expectancy_r=None,account_return_pct=None,account_max_dd_usd=None,
        limitations=['Same inspected frozen candidates; no independent future-period evaluation.',
                    'Weekly closure hypothesis is unauthenticated; original holiday and open-minute unknowns remain.',
                    'Synthetic quote widening, not observed historical stress spreads or comprehensive net costs.',
                    'No rescan of indicators; structural anchors fixed in original price coordinates.',
                    'Reopening gaps may exceed -1R, and deferred timeout may carry across a weekend.',
                    'One-position replay excludes margin, account daily loss and losing-streak controls.'])
    raw=(json.dumps(report,indent=2,allow_nan=False)+'\n').encode();z=gzip.compress(raw,mtime=0)
    manifest=dict(gzip_sha256=sha256(z).hexdigest(),uncompressed_sha256=sha256(raw).hexdigest(),
                  gzip_bytes=len(z),uncompressed_bytes=len(raw),engine_code_sha256=report['engine_code_sha256'],
                  specification_sha256=report['specification_sha256'])
    # Both destinations must be new; do not overwrite prior evidence.
    target=Path(str(stem)+'.json.gz');receipt=Path(str(stem)+'_manifest.json')
    if target.exists() or receipt.exists():raise FileExistsError('New evidence destinations required')
    with target.open('xb') as f:f.write(z)
    with receipt.open('x',encoding='utf-8') as f:json.dump(manifest,f,indent=2);f.write('\n')
    return report


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('stem',type=Path)
    a=p.parse_args();r=run(a.folder,a.stem)
    for window,models in r['results'].items():
        print(window)
        for delta,case in models['PULLBACK_RESUME_FIXED_6'].items():
            print(json.dumps(dict(delta=delta,all=case['all_candidate_summary'],single=case['one_position']['accepted_position_summary'])))
