# SPDX-License-Identifier: GPL-3.0-only
"""One fixed entry-time spread/SL/ATR hypothesis; no adoption or future-price gate."""
import gzip,json
from hashlib import sha256
from math import isfinite
from pathlib import Path
from orrery_paired_archive_study import SOURCE_PINS,read_side,summary
from orrery_pattern_robustness import load_parent,one_position,concentration

ROOT=Path(__file__).resolve().parent
PARENT_STEM=ROOT/'research_evidence/local-history-20261101/pattern_session_spread_20261103'
PARENT_MANIFEST_SHA='a671ac88772f9bde1cad03fbdfe40d4a9cbbb7339119a3cbbf65e71aae4dc3cb'
SPEC=dict(max_entry_spread_to_sl=.10,min_sl_to_atr100=1.,atr_period=100,
          feature_clock='Original confirmed M5 signal at entry decision; entry quote at entry open.',
          grouping='One joint gate on original quotes: spread/SL<=0.10 and SL/ATR100>=1.0.',
          stress='Freeze group membership across additional spread 0/0.3/0.6.',
          unknown='Missing entry/anchor, nonpositive risk or invalid ATR -> UNKNOWN, never PASS.',
          parameter_sets_tried=1,independent_holdout=False,automatic_adoption=False)


def load_stress_parent():
    raw=Path(str(PARENT_STEM)+'_manifest.json').read_bytes()
    if sha256(raw).hexdigest()!=PARENT_MANIFEST_SHA:raise ValueError('Stress manifest changed')
    manifest=json.loads(raw);z=Path(str(PARENT_STEM)+'.json.gz').read_bytes()
    if sha256(z).hexdigest()!=manifest['gzip_sha256']:raise ValueError('Stress archive changed')
    raw=gzip.decompress(z)
    if sha256(raw).hexdigest()!=manifest['uncompressed_sha256']:raise ValueError('Stress evidence changed')
    for name,pin in manifest['engine_code_sha256'].items():
        if sha256((ROOT/name).read_bytes()).hexdigest()!=pin:raise ValueError('Parent engine changed')
    return json.loads(raw)


def entry_features(c,model,bid,ask):
    t=c['entry_at'];side=c['side']
    if side not in ('BUY','SELL') or type(t) is not int:raise ValueError('Entry side and clock required')
    if not model.endswith(('FIXED_6','ANCHOR_EXTREME')):raise ValueError('Explicit SL model required')
    def unknown(reason):return dict(candidate_id=c['id'],entry_at=t,group='UNKNOWN',reason=reason)
    if t not in bid or t not in ask:return unknown('ENTRY_QUOTE_MISSING')
    spread=ask[t]['open']-bid[t]['open']
    if not isfinite(spread) or spread<0:raise ValueError('Noncrossed finite entry quote required')
    entry=ask[t]['open'] if side=='BUY' else bid[t]['open']
    risk=6.
    if model.endswith('ANCHOR_EXTREME'):
        a=c['anchor_open'];known=c['anchor_known_at']
        if type(a) is not int or type(known) is not int or not a<known<=t or (known-a)%60:
            raise ValueError('Confirmed pre-entry anchor required')
        stamps=range(a,known,60)
        if any(x not in bid or x not in ask for x in stamps):return unknown('ANCHOR_QUOTE_MISSING')
        stop=c['anchor_bid_low'] if side=='BUY' else max(ask[x]['high'] for x in stamps)
        risk=entry-stop if side=='BUY' else stop-entry
    atr=c.get('atr')
    if type(atr) not in (int,float) or not isfinite(atr) or atr<=0:return unknown('ATR100_INVALID')
    if not isfinite(risk) or risk<=0:return unknown('NONPOSITIVE_SL_DISTANCE')
    spread_r=spread/risk;sl_atr=risk/atr
    passed=spread_r<=SPEC['max_entry_spread_to_sl'] and sl_atr>=SPEC['min_sl_to_atr100']
    return dict(candidate_id=c['id'],entry_at=t,feature_known_at=t,group='PASS' if passed else 'FAIL',
                original_entry=entry,entry_spread_price=spread,initial_sl_distance=risk,atr100=atr,
                spread_to_sl=spread_r,sl_to_atr100=sl_atr)


def partition_case(rows,features):
    ids=[r['candidate_id'] for r in rows]
    if len(set(ids))!=len(ids) or set(ids)!=set(features):raise ValueError('Exact unique candidate/features required')
    groups={g:[] for g in ('PASS','FAIL','UNKNOWN')}
    for row in rows:
        f=features[row['candidate_id']]
        if f['entry_at']!=row['entry_at']:raise ValueError('Feature entry clock mismatch')
        groups[f['group']].append(row)
    rejected=[r['r'] for r in groups['FAIL'] if r['status']=='RESOLVED_REFERENCE']
    single=one_position(groups['PASS'])
    return dict(baseline=summary(rows),groups={g:summary(rs) for g,rs in groups.items()},
                evaluable_baseline=summary(groups['PASS']+groups['FAIL']),
                missed_positive_reference_r=sum(r for r in rejected if r>0),
                avoided_negative_reference_r=-sum(r for r in rejected if r<0),
                pass_only_one_position=single,pass_resolved_concentration=concentration(groups['PASS']),
                unknown_returns_imputed=False)


def run(folder,stem):
    stress=load_stress_parent();original=load_parent();bid={};ask={}
    for name,pin in SOURCE_PINS.items():
        rows,audit=read_side(Path(folder)/name)
        if audit['sha256']!=pin:raise ValueError('Source changed')
        dest=bid if name.startswith('bid_') else ask
        if set(dest)&set(rows):raise ValueError('Duplicate source clock')
        dest.update(rows)
    if set(bid)!=set(ask):raise ValueError('Exact paired coverage required')
    candidates={c['id']:c for c in original['candidates']};models={};matches=0
    for window,ms in stress['results'].items():
        for model,cases in ms.items():
            base=cases['0.0']['outcomes']
            features={r['candidate_id']:entry_features(candidates[r['candidate_id']],model,bid,ask) for r in base}
            results={}
            for delta,case in cases.items():
                result=partition_case(case['outcomes'],features)
                if result['baseline']!=case['all_candidate_summary']:raise ValueError('Parent baseline changed')
                matches+=1;results[delta]=result
            models.setdefault(window,{})[model]=dict(features=features,cases=results)
    report=dict(status='FIXED_ENTRY_SPREAD_SL_ATR100_COHORT_REVIEW',specification=SPEC,
        specification_sha256=sha256(json.dumps(SPEC,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        parent_manifest_sha256=PARENT_MANIFEST_SHA,source_pins=SOURCE_PINS,models=models,
        case_count=36,all_36_baselines_exact_match=matches==36,
        engine_code_sha256={n:sha256((ROOT/n).read_bytes()).hexdigest() for n in
            ('orrery_pattern_entry_tradeability.py','orrery_pattern_robustness.py','orrery_paired_archive_study.py')},
        adopted=False,execution_allowed=False,out_of_sample=False,formal_lsr02=False,
        net_expectancy_r=None,account_return_pct=None,account_max_dd_usd=None,
        limitations=['Inspected data and a new hypothesis, not independent future validation.',
                    'ATR100 is the original HalfTrend causal ATR, not a new ATR14 optimization.',
                    'Entry quote availability is assumed without latency; execution is not guaranteed.',
                    'Inherited unauthenticated calendar, unknown fees/swaps and quote-widening assumptions.',
                    'PASS/FAIL are cohort labels, not order permission; current risk stops are not bypassed.'])
    raw=(json.dumps(report,indent=2,allow_nan=False)+'\n').encode();z=gzip.compress(raw,mtime=0)
    manifest=dict(gzip_sha256=sha256(z).hexdigest(),uncompressed_sha256=sha256(raw).hexdigest(),
                  engine_code_sha256=report['engine_code_sha256'],specification_sha256=report['specification_sha256'])
    target=Path(str(stem)+'.json.gz');receipt=Path(str(stem)+'_manifest.json')
    if target.exists() or receipt.exists():raise FileExistsError('New destinations required')
    with target.open('xb') as f:f.write(z)
    with receipt.open('x',encoding='utf-8') as f:json.dump(manifest,f,indent=2);f.write('\n')
    return report


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('stem',type=Path)
    a=p.parse_args();r=run(a.folder,a.stem)
    for window,models in r['models'].items():
        print(window)
        for d,c in models['PULLBACK_RESUME_FIXED_6']['cases'].items():print(d,json.dumps(c['groups']))
