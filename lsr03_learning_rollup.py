"""Read-only latest-as-of cohort review of pinned trade-learning cases.

No automatic model fitting or rule promotion. Candidate R is not account PnL.
"""
from hashlib import sha256
from math import isfinite, fsum, isclose
from pathlib import Path
from lsr04_tick_archive import _encode, _decode, _pin, _read_metadata


def _finite(value):
    return type(value) in (int,float) and isfinite(value)


def _load(path, pin):
    _pin(pin); data=_read_metadata(path)
    if sha256(data).hexdigest()!=pin: raise ValueError('Pinned journal bytes changed')
    return _decode(data)


def _outcome(context, result, name):
    if not isinstance(result,dict) or result.get('execution_allowed') is not False:
        raise ValueError('Read-only outcome required')
    status=result.get('status')
    if status not in ('CLOSED','OPEN','NO_ENTRY_QUOTE','INVALID_STRUCTURE'):
        raise ValueError('Unsupported replay outcome')
    if status!='CLOSED':
        if result.get('result')!='UNKNOWN' or result.get('net_price_pnl_per_unit') is not None:
            raise ValueError('Non-closed outcome must remain unknown')
        return None
    plan=context['plans'][name]
    entry=result.get('entry_price'); gross=result.get('gross_price_pnl_per_unit')
    net=result.get('net_price_pnl_per_unit'); cost=context['round_trip_cost_per_unit']
    if (not _finite(entry) or entry<=0 or not _finite(gross)
            or result.get('cost_per_unit')!=cost or result.get('side')!=plan['side']
            or type(result.get('entry_at')) is not int or type(result.get('exit_at')) is not int
            or not context['entry_after_msc']<=result['entry_at']<=result['exit_at']):
        raise ValueError('Closed outcome mismatch')
    distance=entry-plan['stop'] if plan['side']=='BUY' else plan['stop']-entry
    if not _finite(distance) or distance<=0: raise ValueError('Positive initial SL distance required')
    exit_price=result.get('exit_price')
    if not _finite(exit_price) or exit_price<=0: raise ValueError('Positive closing quote required')
    computed=exit_price-entry if plan['side']=='BUY' else entry-exit_price
    if (not _finite(result.get('price_pnl_per_unit'))
            or not isclose(gross,computed,rel_tol=1e-10,abs_tol=1e-10)
            or not isclose(result['price_pnl_per_unit'],gross,rel_tol=1e-10,abs_tol=1e-10)):
        raise ValueError('Gross outcome mismatch')
    if cost is None:
        if net is not None or result.get('result')!='UNKNOWN': raise ValueError('Unknown costs cannot become profit')
        return None
    expected=gross-cost
    if (not _finite(net) or not isclose(net,expected,rel_tol=1e-10,abs_tol=1e-10)
            or result.get('result')!=('WIN' if net>0 else 'LOSS' if net<0 else 'BREAKEVEN')):
        raise ValueError('Net outcome mismatch')
    value=net/distance
    if not isfinite(value): raise ValueError('R overflow')
    return value


def _stats(items, name):
    values=[item[name] for item in items if item[name] is not None]
    profit=fsum(x for x in values if x>0); loss=-fsum(x for x in values if x<0)
    return dict(candidates=len(items),evaluable_closed=len(values),unknown=len(items)-len(values),
                wins=sum(x>0 for x in values),losses=sum(x<0 for x in values),
                breakeven=sum(x==0 for x in values),
                observed_closed_total_candidate_net_r=fsum(values) if values else None,
                all_candidates_evaluable=len(values)==len(items) and bool(items),
                mean_net_r=fsum(values)/len(values) if values else None,
                win_rate=sum(x>0 for x in values)/len(values) if values else None,
                profit_factor=profit/loss if loss else None)


def summarize(cases, *, as_of_msc):
    """cases: explicit path, decision_sha256 and list of retained review_sha256s."""
    if not isinstance(cases,list) or len(cases)>10000 or type(as_of_msc) is not int or as_of_msc<0:
        raise ValueError('Bounded explicit cases and UTC milliseconds required')
    rows=[]; seen=set(); pins=[]; review_count=0; future_reviews=0; cohorts={}; line_kinds={}
    for item in cases:
        if not isinstance(item,dict) or set(item)!={'path','decision_sha256','review_sha256s'}:
            raise ValueError('Explicit case pins required')
        root=Path(item['path'])
        if root.is_symlink() or not root.is_dir(): raise ValueError('Regular case folder required')
        context=_load(root/'decision.json',item['decision_sha256'])
        if (context.get('execution_allowed') is not False or type(context.get('schema_version')) is not int
                or context['schema_version']!=1 or context.get('symbol') not in ('XAUUSD','USDJPY')
                or type(context.get('decision_at_msc')) is not int or context['decision_at_msc']>as_of_msc):
            raise ValueError('Unsupported or future decision')
        key=(context['symbol'],context['strategy_version'],context['candidate_id'])
        if key in seen: raise ValueError('Duplicate candidate in strategy version')
        seen.add(key)
        reviews=item['review_sha256s']
        if not isinstance(reviews,list) or len(reviews)>1000 or len(set(reviews))!=len(reviews):
            raise ValueError('Unique explicit review pins required')
        for pin in reviews: _pin(pin)
        if {p.name for p in root.iterdir()} != {'decision.json',*(f'review-{pin}.json' for pin in reviews)}:
            raise ValueError('Missing or omitted case journal revisions')
        review_count+=len(reviews)
        if review_count>10000: raise ValueError('Review work budget exceeded')
        eligible=[]
        for pin in reviews:
            _pin(pin)
            report=_load(root/('review-'+pin+'.json'),pin)
            if (report.get('status')!='TRADE_REVIEW_HYPOTHESES_ONLY'
                    or report.get('decision_sha256')!=item['decision_sha256']
                    or any(report.get(k)!=context[k] for k in ('candidate_id','symbol','strategy_version',
                                                              'market_regime','levels','entry_thesis'))
                    or any(report.get(k) is not False for k in ('execution_allowed','automatic_rule_update',
                        'strategy_promoted','causal_explanation_verified','cost_verified','account_pnl_available'))
                    or type(report.get('as_of_msc')) is not int):
                raise ValueError('Review context or permission mismatch')
            if report['as_of_msc']>as_of_msc:
                future_reviews+=1; continue
            if report['as_of_msc']<context['entry_after_msc']: raise ValueError('Invalid review clock')
            if not isinstance(report.get('outcomes'),dict) or set(report['outcomes'])!={'original','opposite'}:
                raise ValueError('Both direction outcomes required')
            for name in ('original','opposite'):
                _outcome(context,report['outcomes'][name],name)
                for clock in ('entry_at','exit_at'):
                    if clock in report['outcomes'][name] and report['outcomes'][name][clock]>report['as_of_msc']:
                        raise ValueError('Future fill in saved review')
            eligible.append(report)
        eligible.sort(key=lambda r:r['as_of_msc'])
        if len({r['as_of_msc'] for r in eligible})!=len(eligible):
            raise ValueError('Conflicting reviews at same clock')
        for previous,current in zip(eligible,eligible[1:]):
            for name in ('original','opposite'):
                before,after=previous['outcomes'][name],current['outcomes'][name]
                if before['status'] in ('CLOSED','INVALID_STRUCTURE') and _encode(before)!=_encode(after):
                    raise ValueError('Terminal outcome changed between reviews')
                if 'entry_at' in before and any(before.get(k)!=after.get(k) for k in ('entry_at','entry_price')):
                    raise ValueError('Entry changed between revisions')
        latest=eligible[-1] if eligible else None
        row=dict(original=None,opposite=None,reviewed=latest is not None)
        if latest:
            row.update({name:_outcome(context,latest['outcomes'][name],name) for name in ('original','opposite')})
        levels=context['levels']
        proximity='UNAVAILABLE' if not levels else 'NEAR' if any(l['near_reference'] for l in levels) else 'NOT_NEAR'
        cohort=(*key[:2],context['market_regime'],proximity)
        cohorts.setdefault(cohort,[]).append(row)
        for kind in sorted({level['kind'] for level in levels if level['near_reference']}):
            line_kinds.setdefault((*key[:2],kind),[]).append(row)
        rows.append(row); pins.append(dict(decision=item['decision_sha256'],reviews=sorted(reviews)))
    def grouped(groups,labels):
        return [dict(zip(labels,key),original=_stats(items,'original'),opposite=_stats(items,'opposite'))
                for key,items in sorted(groups.items())]
    paired=[r for r in rows if r['original'] is not None and r['opposite'] is not None]
    return dict(status='DESCRIPTIVE_LEARNING_COHORTS_ONLY',as_of_msc=as_of_msc,case_versions=len(rows),
        unique_symbol_candidate_pairs=len({(symbol,candidate) for symbol,_,candidate in seen}),
        reviewed=sum(r['reviewed'] for r in rows),unreviewed=sum(not r['reviewed'] for r in rows),
        future_reviews_ignored=future_reviews,cohorts=grouped(cohorts,
            ('symbol','strategy_version','market_regime','level_proximity')),
        near_line_kind_cohorts=grouped(line_kinds,('symbol','strategy_version','level_kind')),
        paired_counts=dict(evaluable=len(paired),both_lost=sum(r['original']<0 and r['opposite']<0 for r in paired),
            original_lost_opposite_won=sum(r['original']<0 and r['opposite']>0 for r in paired),
            original_won_opposite_lost=sum(r['original']>0 and r['opposite']<0 for r in paired)),
        source_pins_sha256=sha256(_encode(pins)).hexdigest(),
        candidate_r_not_account_return=True,line_kind_groups_overlap=True,
        causal_explanation_verified=False,market_edge_verified=False,
        automatic_rule_update=False,strategy_promoted=False,execution_allowed=False)
