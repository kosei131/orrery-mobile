"""Offline DEMO order drafts, never a broker request or execution permission."""
from copy import deepcopy
from hashlib import sha256
from decimal import Decimal
from math import isfinite
from lsr02_risk_plan import plan
from lsr04_tick_archive import _encode


def prepare(*, snapshot, side, sweep_extreme, buffer, target, lots, guards, now_msc):
    keys={'account_token','mode','symbol','bid','ask','quote_msc','volume_min','volume_max',
          'volume_step','broker_loss_one_lot','spec_token'}
    if not isinstance(snapshot,dict) or set(snapshot)!=keys:
        raise ValueError('Exact DEMO snapshot required')
    s=deepcopy(snapshot)
    if (s['mode']!='DEMO' or s['symbol'] not in ('XAUUSD','USDJPY')
            or any(not isinstance(s[k],str) or not s[k] for k in ('account_token','spec_token'))
            or side not in ('BUY','SELL') or type(now_msc) is not int
            or type(s['quote_msc']) is not int or not 0<=now_msc-s['quote_msc']<=5000):
        raise ValueError('Supported fresh DEMO quote required')
    nums=[s[k] for k in ('bid','ask','volume_min','volume_max','volume_step','broker_loss_one_lot')]+[lots]
    if any(type(x) not in (int,float) or not isfinite(x) or x<=0 for x in nums):
        raise ValueError('Positive finite quote and sizing required')
    if s['bid']>s['ask']:raise ValueError('Crossed quote')
    d=Decimal(str(lots));step=Decimal(str(s['volume_step']))
    if not s['volume_min']<=lots<=s['volume_max'] or d%step:
        raise ValueError('Broker volume bounds and step required')
    entry=s['ask'] if side=='BUY' else s['bid']
    result=plan(side=side,entry=entry,sweep_extreme=sweep_extreme,buffer=buffer,target=target,**guards)
    actual_stop_risk=lots*s['broker_loss_one_lot']
    cost=guards.get('cost')
    if result['status']!='DEMO_REVIEW_ONLY':raise ValueError('Existing risk plan blocked')
    if not isfinite(actual_stop_risk) or actual_stop_risk>result['gross_stop_risk_usd']:
        raise ValueError('Lot risk exceeds planned allowance')
    rr=abs(target-entry)/abs(entry-result['stop'])
    net_rr=(actual_stop_risk*rr-cost)/(actual_stop_risk+cost)
    if net_rr<2:raise ValueError('Actual-size cost-adjusted RR below existing minimum')
    payload=dict(status='DEMO_ORDER_DRAFT_ONLY',snapshot=s,side=side,entry=entry,
        stop=result['stop'],target=target,lots=lots,stop_risk_assumption=actual_stop_risk,
        net_rr=net_rr,expires_msc=s['quote_msc']+5000,
        guards=deepcopy(guards),sweep_extreme=sweep_extreme,buffer=buffer,
        broker_snapshot_authenticated=False,broker_stops_and_margin_checked=False,
        execution_allowed=False)
    return dict(payload,draft_sha256=sha256(_encode(payload)).hexdigest())


def recheck(draft, *, current_snapshot, current_guards, now_msc):
    stored=deepcopy(draft);pin=stored.pop('draft_sha256')
    if sha256(_encode(stored)).hexdigest()!=pin:raise ValueError('Draft changed')
    if stored['snapshot']!=current_snapshot or stored['guards']!=current_guards:
        raise ValueError('Account, quote, specification or risk context changed')
    fresh=prepare(snapshot=current_snapshot,side=stored['side'],sweep_extreme=stored['sweep_extreme'],
        buffer=stored['buffer'],target=stored['target'],lots=stored['lots'],guards=current_guards,now_msc=now_msc)
    if fresh!=draft:raise ValueError('Draft recomputation mismatch')
    return dict(status='DRAFT_RECHECKED_NOT_ORDER_AUTHORIZATION',execution_allowed=False)
