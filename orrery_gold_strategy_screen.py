# SPDX-License-Identifier: GPL-3.0-only
"""Fail-closed read-only scorecard for inspected Gold strategy results.

Thresholds are research screening criteria, not statistically calibrated
deployment rules. The inputs are historical inspected data, never OOS.
"""
import argparse
import json
from pathlib import Path

EXPECTED_SOURCE='a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225'
MODELS=(
    'ALL_CONFIRMATION_FIXED_6','ALL_CONFIRMATION_SWEEP_EXTREME',
    'ALL_RETEST_FIXED_6','ALL_RETEST_SWEEP_EXTREME',
    'VHF_PASS_CONFIRMATION_FIXED_6','VHF_PASS_CONFIRMATION_SWEEP_EXTREME',
    'VHF_PASS_RETEST_FIXED_6','VHF_PASS_RETEST_SWEEP_EXTREME')
SPREADS=('0.6','1.2','2.0')
MIN_RESOLVED=30


def _positive(x):
    return type(x) in (int,float) and x > 0 and x < float('inf')


def evaluate(evidence):
    if (not isinstance(evidence,dict)
        or evidence.get('raw_source_sha256')!=EXPECTED_SOURCE
        or evidence.get('out_of_sample') is not False
        or evidence.get('baseline_all_eight_models_exact_match') is not True):
        raise ValueError('Unexpected or unverified historical evidence')
    models=evidence.get('models')
    if not isinstance(models,dict) or set(models)!=set(MODELS):
        raise ValueError('All eight fixed models required')
    output={}
    for name in MODELS:
        scenarios=models[name]
        if not isinstance(scenarios,dict) or not set(SPREADS).issubset(scenarios):
            raise ValueError('All fixed spread scenarios required')
        base=scenarios['0.6']
        trend=base['stability']
        n=base['entry_outcomes']['resolved_outcomes']
        if type(n) is not int or n<0 or n>base['entry_outcomes']['candidates']:
            raise ValueError('Invalid resolved denominator')
        flags=dict(
            sufficient_resolved=n>=MIN_RESOLVED,
            positive_reference_mean=_positive(base['entry_outcomes']['mean_r']),
            positive_both_chronological_halves=all(
                _positive(trend[k]['mean_reference_r']) for k in ('before_cut','from_cut')),
            survives_worst_spread=_positive(scenarios['2.0']['entry_outcomes']['mean_r']),
            survives_best_month_removal=_positive(trend['excluding_best_month']['mean_reference_r']))
        output[name]=dict(resolved=n,
                          observed_win_rate_pct=base['entry_outcomes']['win_rate_pct'],
                          observed_mean_r=base['entry_outcomes']['mean_r'],
                          observed_pf=base['entry_outcomes']['pf'],
                          conditions=flags, passes_exploratory_screen=all(flags.values()),
                          out_of_sample_validated=False, broker_costs_validated=False,
                          adoption_allowed=False)
    return dict(status='INSPECTED_GOLD_RESEARCH_SCREEN_ONLY',
                input_source_sha256=EXPECTED_SOURCE, screening_min_resolved=MIN_RESOLVED,
                models=output, eligible_models=[n for n in MODELS if output[n]['passes_exploratory_screen']],
                strategy_adoption_allowed=False, actual_account_return_pct=None,
                net_expectancy_r=None, out_of_sample=False, execution_allowed=False)


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('evidence')
    p.add_argument('output')
    a=p.parse_args(argv)
    out=Path(a.output)
    if out.exists() or out.is_symlink():
        p.error('Refusing to overwrite output')
    report=evaluate(json.loads(Path(a.evidence).read_text(encoding='utf-8')))
    with out.open('x',encoding='utf-8') as f:
        json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({n:x['conditions'] for n,x in report['models'].items()}))


if __name__=='__main__':
    main()
