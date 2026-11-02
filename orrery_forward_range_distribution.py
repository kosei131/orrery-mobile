"""Descriptive train/holdout range distribution, not calibrated forecasts."""
from math import isfinite

def _quantile(values,q):
    xs=sorted(values)
    k=(len(xs)-1)*q
    i=int(k)
    return xs[i]+(xs[min(i+1,len(xs)-1)]-xs[i])*(k-i)

def summarize(study, *, split_at, min_train=30, min_holdout=30):
    if (study.get('status')!='OFFLINE_FORWARD_LABELS_NOT_PREDICTIONS'
        or study.get('execution_allowed') is not False
        or type(split_at) is not int or type(min_train) is not int
        or type(min_holdout) is not int or min_train<2 or min_holdout<2):
        raise ValueError('Pinned descriptive study and split required')
    rows=study['rows'];horizons=study['horizons']
    if not isinstance(rows,list) or not 1<=len(rows)<=100000:
        raise ValueError('Bounded rows required')
    seen=set();train=[];holdout=[];excluded=[]
    for r in rows:
        t=r['decision_at'];f=r['features']
        if type(t) is not int or t in seen or f['latest_closed_at']!=t:
            raise ValueError('Unique causal decisions required')
        seen.add(t)
        labels=r['future_label_only']
        if set(labels)!=set(map(str,horizons)):
            raise ValueError('All horizon labels required')
        for h in horizons:
            o=labels[str(h)]
            if any(type(o[k]) not in (int,float) or not isfinite(o[k])
                for k in ('maximum_favorable_move','maximum_adverse_move','closing_change')):
                raise ValueError('Finite range outcomes required')
        # Do not allow training labels that overlap the untouched test interval.
        max_h=max(horizons)
        interval=f.get('interval_seconds',300)
        if type(interval) is not int or interval<=0:raise ValueError('Explicit bar interval required')
        if t<split_at and t+max_h*interval>=split_at: excluded.append(r)
        elif t<split_at:train.append(r)
        else:holdout.append(r)
    def stats(cohort):
        output={}
        for h in horizons:
            series=[r['future_label_only'][str(h)] for r in cohort]
            output[str(h)]=dict(samples=len(series),
                up_q10=_quantile([r['maximum_favorable_move'] for r in series],.1) if series else None,
                up_q50=_quantile([r['maximum_favorable_move'] for r in series],.5) if series else None,
                up_q90=_quantile([r['maximum_favorable_move'] for r in series],.9) if series else None,
                down_q50=_quantile([r['maximum_adverse_move'] for r in series],.5) if series else None,
                down_q90=_quantile([r['maximum_adverse_move'] for r in series],.9) if series else None,
                close_q50=_quantile([r['closing_change'] for r in series],.5) if series else None)
        return output
    return dict(status='DESCRIPTIVE_RANGE_DISTRIBUTION_NOT_FORECAST',
        train_samples=len(train),holdout_samples=len(holdout),excluded_at_boundary=len(excluded),
        sample_gate_passed=len(train)>=min_train and len(holdout)>=min_holdout,
        training=stats(train),holdout_observed=stats(holdout),
        probabilities_calibrated=False,prediction_quality_verified=False,
        live_future_candles=None,net_profit_usd=None,execution_allowed=False)
