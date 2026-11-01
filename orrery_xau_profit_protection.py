"""Fixed profit-protection hypotheses; minute bars, no broker fills or orders."""
import csv,json,hashlib,math
from pathlib import Path
from datetime import datetime
from orrery_xau_hypothetical_pnl import simulate

POLICIES=('BASELINE_2R','PRICE_BE_AFTER_1R','HALF_AT_1R','HALF_AT_1R_AND_PRICE_BE')


def replay(bars, *, side, policy, spread=.6, distance=6., horizon=120):
    if (policy not in POLICIES or side not in ('BUY','SELL') or type(horizon) is not int or horizon<1
            or not all(type(x) in (int,float) and math.isfinite(x) for x in (spread,distance))
            or spread<0 or distance<=0):raise ValueError('Explicit valid research settings required')
    if not bars:return dict(status='UNKNOWN',r=None,partial_r=0.)
    entry=bars[0][1]+spread if side=='BUY' else bars[0][1]
    direction=1 if side=='BUY' else -1
    stop=entry-direction*distance;target=entry+direction*2*distance
    trigger=entry+direction*distance;remaining=1.;realized=0.;pending=False;partial=False
    previous=None;last=None
    for index,b in enumerate(bars[:horizon]):
        if previous is not None and b[0]-previous!=60:break
        previous=b[0];last=b
        if pending:stop=entry;pending=False
        opened=b[1] if side=='BUY' else b[1]+spread
        high=b[2] if side=='BUY' else b[2]+spread
        low=b[3] if side=='BUY' else b[3]+spread
        stopped=low<=stop if side=='BUY' else high>=stop
        if stopped:
            adverse_open=opened<=stop if side=='BUY' else opened>=stop
            fill=opened if adverse_open else stop
            return dict(status='CLOSED',r=realized+remaining*direction*(fill-entry)/distance,partial_r=realized)
        hit1=high>=trigger if side=='BUY' else low<=trigger
        hit2=high>=target if side=='BUY' else low<=target
        if hit1:
            if policy in ('HALF_AT_1R','HALF_AT_1R_AND_PRICE_BE') and not partial:
                realized+=.5;remaining=.5;partial=True
            if policy in ('PRICE_BE_AFTER_1R','HALF_AT_1R_AND_PRICE_BE'):pending=True
        if hit2:return dict(status='CLOSED',r=realized+remaining*2,partial_r=realized)
        if index+1==horizon:
            close=b[4] if side=='BUY' else b[4]+spread
            return dict(status='CLOSED',r=realized+remaining*direction*(close-entry)/distance,partial_r=realized)
    return dict(status='UNKNOWN',r=None,partial_r=realized)


def run():
    m1=Path('public_xau_bars/XAUUSD_M1_UNVERIFIED_QUOTE.csv');src=Path('public_xau_sequence_report.json')
    with m1.open(newline='',encoding='utf-8') as f:
        bars=[(int(datetime.fromisoformat(x['timestamp_utc']).timestamp()),*[float(x[k]) for k in
               ('bid_open','bid_high','bid_low','bid_close')]) for x in csv.DictReader(f)]
    indices={b[0]:i for i,b in enumerate(bars)}
    candidates=json.loads(src.read_text())['retouch_evidence'];rows=[];seen=set()
    baseline=simulate(m1,src,reward_r=2.)
    ref={(t['touch_close_utc'],t['side']):t['r'] for t in baseline['trades_detail']}
    for c in candidates:
        at=c['first_poi_touch_close'];side=c['side'];key=(at,side)
        if key in seen:raise ValueError('Duplicate candidate')
        seen.add(key);i=indices.get(at);future=bars[i:i+120] if i is not None else []
        outcomes={p:replay(future,side=side,policy=p) for p in POLICIES}
        base=outcomes['BASELINE_2R']['r']
        if (key in ref)!=(base is not None) or (base is not None and abs(base-ref[key])>1e-5):
            raise ValueError('Baseline disagrees with existing fixed-exit engine')
        rows.append(dict(at=at,side=side,outcomes=outcomes))
    results={}
    for p in POLICIES:
        values=[r['outcomes'][p]['r'] for r in rows if r['outcomes'][p]['r'] is not None]
        paired=[r for r in rows if r['outcomes'][p]['r'] is not None and r['outcomes']['BASELINE_2R']['r'] is not None]
        results[p]=dict(candidates=len(rows),closed=len(values),unknown=len(rows)-len(values),
            wins=sum(v>0 for v in values),mean_resolved_r=sum(values)/len(values) if values else None,
            observed_total_r=sum(values) if values else None,
            paired_diagnostic_only=dict(count=len(paired),
                baseline_wins_reduced=sum(r['outcomes']['BASELINE_2R']['r']>0 and r['outcomes'][p]['r']<r['outcomes']['BASELINE_2R']['r'] for r in paired),
                baseline_losses_improved=sum(r['outcomes']['BASELINE_2R']['r']<0 and r['outcomes'][p]['r']>r['outcomes']['BASELINE_2R']['r'] for r in paired)))
    report=dict(status='IN_SAMPLE_FIXED_PROTECTION_NOT_ADOPTED',results=results,rows=rows,
        source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (m1,src)},
        assumptions=dict(spread_price_units=.6,initial_stop_price_units=6,target_r=2,trigger_r=1,
            horizon_minutes=120,be_activation='NEXT_OBSERVED_MINUTE_ONLY',same_bar='STOP_FIRST',
            partial_extra_fees_modeled=False),
        warnings=['PUBLIC_QUOTE_NOT_BROKER_BID_ASK','PRICE_BREAKEVEN_BEFORE_FEES',
            'NO_COMMISSION_SLIPPAGE_SWAP','NO_ACCOUNT_RETURN_OR_DRAWDOWN',
            'PAIRED_CLOSED_SUBSET_SELECTION_BIAS','ALREADY_INSPECTED_DATA_NOT_OUT_OF_SAMPLE'],
        adopted=False,execution_allowed=False)
    Path('public_xau_profit_protection.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'}));return report

if __name__=='__main__':run()
