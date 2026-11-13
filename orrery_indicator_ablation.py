# SPDX-License-Identifier: GPL-3.0-only
"""Single-indicator entry cohort filters; inspected-data price R, no adoption."""
from bisect import bisect_right
from collections import Counter
import csv
from hashlib import sha256
import json
from math import sqrt
from pathlib import Path
from tempfile import TemporaryDirectory
from orrery_indicator_diagnostics import diagnostics
from orrery_real_bars_lsr_bridge import load
from orrery_m1_complete_bars import aggregate
from orrery_entry_universe_study import confirmations
from orrery_public_xau_sequence_study import observe_retest
from orrery_xau_confirmation_entry_comparison import entry_plans
from orrery_xau_h4_alignment import START, END
from orrery_paired_archive_study import read_side, iso, summary

ROOT=Path(__file__).resolve().parent
GETDATA='research_evidence/local-history-20261101/entry_universe_profitability_20261102.json'
PAIRED='research_evidence/local-history-20261101/paired_archive_study_20261102.json'
PINS={GETDATA:'d298984ce96981f63cddad50886217de530431a78c1b8b50f1f4ba60e35a21dd',
      PAIRED:'a67972316ed9140150ccdcf42ed88532f9035400f2131cce50ece667f8a65946'}
RULES=('EMA20_50_DIRECTION','ADX14_GE25','MACD12_26_9_HISTOGRAM',
       'ICHIMOKU9_26_52_CURRENT_CLOUD','BB20_2_BREAKOUT','DONCHIAN20_BREAKOUT','ATR14_EXPANSION')


def ema_series(values,p):
    out=[None]*len(values)
    if len(values)<p:return out
    v=sum(values[:p])/p;out[p-1]=v;k=2/(p+1)
    for i in range(p,len(values)):
        v+=k*(values[i]-v);out[i]=v
    return out


def feature_values(bars,as_of):
    if type(as_of) is not int:raise ValueError('Integer decision clock required')
    times=[b['close_time'] for b in bars]
    if any(b<=a for a,b in zip(times,times[1:])):raise ValueError('Ordered M5 required')
    i=bisect_right(times,as_of)
    out=dict(as_of=as_of,samples=0,latest_closed_at=None)
    if not i or times[i-1]!=as_of:return out
    a=i-1
    while a>0 and i-a<300 and times[a]-times[a-1]==300:a-=1
    h=bars[a:i];out.update(samples=len(h),latest_closed_at=times[i-1])
    if len(h)<2:return out
    d=diagnostics(h,as_of=as_of,interval=300)
    out.update(ema20=d['ema_fast'],ema50=d['ema_slow'],adx14=d['adx'],atr14=d['atr'])
    close=[b['close'] for b in h];out['close']=close[-1]
    fast=ema_series(close,12);slow=ema_series(close,26)
    line=[f-s for f,s in zip(fast,slow) if f is not None and s is not None]
    sig=ema_series(line,9)
    out['macd_histogram']=line[-1]-sig[-1] if line and sig[-1] is not None else None
    if len(h)>=20:
        values=close[-20:];mean=sum(values)/20
        sd=sqrt(sum((c-mean)**2 for c in values)/20)
        out.update(bb_upper=mean+2*sd,bb_lower=mean-2*sd)
    if d['donchian'] is not None:out.update(donchian_upper=d['donchian']['previous_upper'],donchian_lower=d['donchian']['previous_lower'])
    if len(h)>=78:
        old=h[:-26]
        def mid(p):return (max(b['high'] for b in old[-p:])+min(b['low'] for b in old[-p:]))/2
        span_a=(mid(9)+mid(26))/2;span_b=mid(52)
        out.update(current_cloud_top=max(span_a,span_b),current_cloud_bottom=min(span_a,span_b),
                   cloud_calculated_at=old[-1]['close_time'])
    tr=[max(h[i]['high']-h[i]['low'],abs(h[i]['high']-h[i-1]['close']),abs(h[i]['low']-h[i-1]['close'])) for i in range(1,len(h))]
    atr=[]
    if len(tr)>=14:
        v=sum(tr[:14])/14;atr=[v]
        for t in tr[14:]:v=(13*v+t)/14;atr.append(v)
    out['prior20_atr_mean']=sum(atr[-21:-1])/20 if len(atr)>=21 else None
    return out


def classify(f,side):
    if side not in ('BUY','SELL'):raise ValueError('Explicit side required')
    up=side=='BUY';result={}
    def directional(a,b):return a>b if up else a<b
    pairs={
        RULES[0]:('ema20','ema50'),RULES[3]:('close','current_cloud_top' if up else 'current_cloud_bottom'),
        RULES[4]:('close','bb_upper' if up else 'bb_lower'),
        RULES[5]:('close','donchian_upper' if up else 'donchian_lower')}
    for name,(a,b) in pairs.items():result[name]=None if f.get(a) is None or f.get(b) is None else directional(f[a],f[b])
    result[RULES[1]]=None if f.get('adx14') is None else f['adx14']>=25
    result[RULES[2]]=None if f.get('macd_histogram') is None else directional(f['macd_histogram'],0)
    result[RULES[6]]=None if f.get('atr14') is None or f.get('prior20_atr_mean') is None else f['atr14']>f['prior20_atr_mean']
    return {name:result[name] for name in RULES}


def compare(rows,bars):
    times={};features=[]
    for r in rows:
        t=r['entry_at']
        if t not in times:times[t]=feature_values(bars,t)
        features.append(dict(entry_at=t,side=r['side'],values=times[t],decisions=classify(times[t],r['side'])))
    out={}
    for rule in RULES:
        groups={g:[] for g in ('PASS','FAIL','UNKNOWN')}
        for r,f in zip(rows,features):
            d=f['decisions'][rule];groups['UNKNOWN' if d is None else 'PASS' if d else 'FAIL'].append(r)
        rejected=groups['FAIL'];known=[r['r'] for r in rejected if r['status']=='RESOLVED_REFERENCE']
        out[rule]=dict(groups={g:summary(rs) for g,rs in groups.items()},
            evaluable_baseline=summary(groups['PASS']+groups['FAIL']),
            missed_positive_reference_r=sum(r for r in known if r>0),
            avoided_negative_reference_r=-sum(r for r in known if r<0),
            unknown_reference_r_not_imputed=True)
    return dict(baseline=summary(rows),filters=out,features=features)


def pinned_evidence(name):
    raw=(ROOT/name).read_bytes()
    if sha256(raw).hexdigest()!=PINS[name]:raise ValueError('Evidence hash mismatch')
    return json.loads(raw)


def paired_bars(folder,evidence):
    bids={}
    for item in evidence['files']:
        p=folder/(item['side']+'_'+item['month']+'.csv')
        if sha256(p.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Paired source changed')
        if item['side']=='bid':
            rows,_=read_side(p)
            if set(rows)&set(bids):raise ValueError('Duplicate source time')
            bids.update(rows)
    with TemporaryDirectory() as tmp:
        src=Path(tmp)/'m1.csv';dst=Path(tmp)/'m5.csv'
        with src.open('w',newline='') as f:
            w=csv.writer(f);w.writerow(['timestamp_utc','bid_open','bid_high','bid_low','bid_close'])
            for t,b in sorted(bids.items()):w.writerow([iso(t),b['open'],b['high'],b['low'],b['close']])
        aggregate(src,dst,'M5');return load(dst,'M5')['bars']


def run(getdata_root,paired_root,output):
    old=pinned_evidence(GETDATA);paired=pinned_evidence(PAIRED)
    folder=Path(getdata_root)/'public_xau_bars'
    for name,pin in old['source_hashes'].items():
        if sha256((folder/name).read_bytes()).hexdigest()!=pin:raise ValueError('GetData source changed')
    m5=load(folder/'XAUUSD_M5_UNVERIFIED_QUOTE.csv','M5')['bars']
    m15=load(folder/'XAUUSD_M15_UNVERIFIED_QUOTE.csv','M15')['bars']
    cs=[c for c in confirmations(m15,m5) if START<=c['confirmation_close']<END]
    obs={(c['sweep_close'],c['confirmation_close'],c['side']):observe_retest(c,m5) for c in cs}
    models={}
    for scope,subset in (('ALL',cs),('VHF_PASS',[c for c in cs if c['vhf_pass']])):
        for mode in ('CONFIRMATION','RETEST'):
            plans,skips=entry_plans(subset,mode=mode,observations=obs)
            for policy in ('FIXED_6','SWEEP_EXTREME'):
                label=scope+'_'+mode+'_'+policy;source=old['results'][label]
                if len(plans)!=source['entry_plans']:raise ValueError('Plan population changed')
                detail={(r['touch_close_utc'],r['side']):r for r in source['trades_detail']};rows=[]
                identities={(p['first_poi_touch_close'],p['side']) for p in plans}
                if not set(detail)<=identities:raise ValueError('Outcome outside planned population')
                for p in plans:
                    key=(p['first_poi_touch_close'],p['side']);t=detail.get(key)
                    r=dict(entry_at=key[0],side=key[1],status='RESOLVED_REFERENCE' if t else 'UNMODELED_OR_SKIPPED')
                    if t:r['r']=t['r']
                    rows.append(r)
                result=compare(rows,m5)
                if result['baseline']['resolved']!=source['entry_outcomes']['resolved_outcomes']:raise ValueError('Baseline changed')
                result['source_no_entry_reasons']=source['no_entry_reasons']
                result['source_stop_policy_skip_counts']=source['stop_policy_skip_counts']
                result['source_incomplete_after_entry']=source['incomplete_after_entry']
                models['GETDATA_5MONTH/'+label]=result
    other=paired_bars(Path(paired_root),paired)
    for window,w in paired['results'].items():
        for label,source in w['models'].items():
            result=compare(source['outcomes'],other)
            if result['baseline']!={k:source[k] for k in result['baseline']}:raise ValueError('Paired baseline changed')
            result['source_no_entry_reasons']=source['no_entry_reasons']
            models['PAIRED_'+window+'/'+label]=result
    report=dict(status='EXPLORATORY_SINGLE_INDICATOR_COHORT_ABLATION',
        models=models,filters=list(RULES),model_count=len(models),comparison_count=len(models)*len(RULES),
        source_evidence_sha256=PINS,code_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        baseline_all_models_reconciled=True,execution_allowed=False,adopted=False,
        out_of_sample=False,external_indicator_parity_verified=False,
        net_expectancy_r=None,account_return_pct=None,account_max_dd_usd=None,
        limitations=['Same inspected periods; many correlated comparisons, no automatic selection.',
            'Price reference outcomes reused from pinned evidence; no new execution or risk-control replay.',
            'Feature time is entry-decision closed M5; gaps reset context, maximum 300 bars.',
            'EMA/MACD SMA initialization; current cloud is strictly 26-bar-displaced research convention.',
            'Filtered single-trade cohorts do not simulate changing candidate state, portfolio or account stops.',
            'Unknown feature history and unmodeled outcomes remain separately reported.'])
    with Path(output).open('x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({name:{rule:{'pass':v['groups']['PASS'],'fail':v['groups']['FAIL'],'unknown':v['groups']['UNKNOWN']} for rule,v in model['filters'].items()} for name,model in models.items()}))
    return report

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('getdata_root',type=Path);p.add_argument('paired_root',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();run(a.getdata_root,a.paired_root,a.output)
