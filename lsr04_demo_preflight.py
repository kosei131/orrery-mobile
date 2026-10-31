"""Read-only broker constraints and margin estimate. Not order authorization."""
from decimal import Decimal
from math import isfinite
from lsr03_mt5_pilot import _account,_valuation_spec
from lsr04_mt5_order_draft import read_draft


def review(mt5, **draft_args):
    symbol=draft_args['symbol'];side=draft_args['side']
    identity=_account(mt5)
    def state():
        a=mt5.account_info();t=mt5.terminal_info();s=mt5.symbol_info(symbol)
        if a is None or t is None or s is None:raise ValueError('Broker state unavailable')
        if (getattr(a,'trade_allowed',None) is not True or getattr(a,'trade_expert',None) is not True
                or getattr(t,'connected',None) is not True or getattr(t,'trade_allowed',None) is not True
                or getattr(t,'tradeapi_disabled',None) is not False):
            raise ValueError('Account or terminal trading disabled or unknown')
        equity=getattr(a,'equity',None)
        if type(equity) not in (int,float) or not isfinite(equity) or equity<=0:raise ValueError('Equity unavailable')
        free=getattr(a,'margin_free',None)
        if type(free) not in (int,float) or not isfinite(free) or free<=0:raise ValueError('Free margin unavailable')
        names=('trade_mode','order_mode','trade_stops_level','trade_freeze_level')
        caps={k:getattr(s,k,None) for k in names}
        if any(type(v) is not int or v<0 for v in caps.values()):raise ValueError('Symbol permissions unavailable')
        # Official ENUM_SYMBOL_TRADE_MODE: 1 long-only, 2 short-only, 4 full.
        if caps['trade_mode'] not in ((1,4) if side=='BUY' else (2,4)):
            raise ValueError('Symbol direction not enabled for new trades')
        # Official SYMBOL_ORDER_* bits: MARKET=1, SL=16, TP=32.
        if caps['order_mode'] & 49 !=49:raise ValueError('Market order with SL and TP unsupported')
        for k in ('point','trade_tick_size'):
            value=getattr(s,k,None)
            if type(value) not in (int,float) or not isfinite(value) or value<=0:raise ValueError('Price grid unavailable')
            caps[k]=value
        return dict(equity=equity,free=free,caps=caps,valuation=_valuation_spec(mt5,symbol))
    before=state();result=read_draft(mt5,**draft_args);draft=result['draft'];q=draft['snapshot']
    caps=before['caps'];D=lambda x:Decimal(str(x))
    tick=D(caps['trade_tick_size'])
    if any(D(draft[k])%tick for k in ('stop','target')):raise ValueError('SL/TP off broker price grid')
    close=q['bid'] if side=='BUY' else q['ask']
    distances=(D(close)-D(draft['stop']),D(draft['target'])-D(close)) if side=='BUY' else (D(draft['stop'])-D(close),D(close)-D(draft['target']))
    # Conservative draft-only freeze buffer, not a claim that new orders use
    # the same freeze rules as modification of existing positions.
    minimum=D(caps['point'])*max(caps['trade_stops_level'],caps['trade_freeze_level'])
    if any(v<=0 or v<minimum for v in distances):raise ValueError('SL/TP too near closing quote')
    action=mt5.ORDER_TYPE_BUY if side=='BUY' else mt5.ORDER_TYPE_SELL
    margin=mt5.order_calc_margin(action,symbol,draft['lots'],draft['entry'])
    if type(margin) not in (int,float) or not isfinite(margin) or margin<=0:
        raise ValueError('Margin calculation unavailable')
    if D(margin)+D(draft['guards']['cost'])>D(before['free']):raise ValueError('Insufficient estimated free margin')
    latest=mt5.symbol_info_tick(symbol)
    if (_account(mt5)!=identity or state()!=before or latest is None
            or (latest.bid,latest.ask,latest.time_msc)!=(q['bid'],q['ask'],q['quote_msc'])):
        raise ValueError('Broker context changed during preflight')
    return dict(status='DEMO_PREFLIGHT_REVIEW_ONLY',draft_result=result,
        broker_constraints=before,estimated_margin=margin,
        minimum_distance_checked=True,margin_estimate_checked=True,permission_flags_checked=True,
        min_distance_policy='MAX_STOPS_AND_FREEZE_CONSERVATIVE',
        margin_includes_pending_orders_and_positions=False,
        broker_session_verified=False,order_check_performed=False,execution_allowed=False)
