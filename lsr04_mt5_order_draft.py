"""Read-only DEMO snapshot and exact structural-SL valuation. No order calls."""
from copy import deepcopy
from hashlib import sha256
from math import isfinite
from secrets import token_hex
from lsr03_mt5_pilot import _account,_valuation_spec
from lsr04_tick_archive import _encode
from lsr04_demo_order_draft import prepare


def read_draft(mt5, *, symbol, side, sweep_extreme, buffer, target, lots, guards,
               now_msc, account_nonce=None):
    if symbol not in ('XAUUSD','USDJPY') or side not in ('BUY','SELL'):
        raise ValueError('Exact supported symbol and side required')
    identity=_account(mt5)
    def account_view():
        a=mt5.account_info()
        if a is None or getattr(a,'trade_mode',None)!=mt5.ACCOUNT_TRADE_MODE_DEMO or getattr(a,'currency',None)!='USD':
            raise ValueError('USD DEMO required by USD risk planner')
        equity=getattr(a,'equity',None)
        if type(equity) not in (int,float) or not isfinite(equity) or equity<=0:
            raise ValueError('Finite equity required')
        return equity
    equity=account_view();spec=_valuation_spec(mt5,symbol)
    if spec is None:raise ValueError('Complete broker valuation specification required')
    if guards.get('equity')!=equity:raise ValueError('Risk-plan equity differs from current account')
    def quote():
        t=mt5.symbol_info_tick(symbol)
        if t is None:raise ValueError('Quote unavailable')
        result=dict(bid=getattr(t,'bid',None),ask=getattr(t,'ask',None),quote_msc=getattr(t,'time_msc',None))
        if (type(result['quote_msc']) is not int or type(now_msc) is not int
                or not 0<=now_msc-result['quote_msc']<=5000
                or any(type(result[k]) not in (int,float) or not isfinite(result[k]) or result[k]<=0 for k in ('bid','ask'))
                or result['bid']>result['ask']):raise ValueError('Fresh uncrossed quote required')
        return result
    q=quote();entry=q['ask'] if side=='BUY' else q['bid']
    if any(type(x) not in (int,float) or not isfinite(x) or x<=0 for x in (sweep_extreme,buffer,target)):
        raise ValueError('Positive structural levels required')
    sl=sweep_extreme-buffer if side=='BUY' else sweep_extreme+buffer
    if not (0<sl<entry<target if side=='BUY' else 0<target<entry<sl):raise ValueError('Adverse structural SL required')
    if not (sl<q['bid'] if side=='BUY' else sl>q['ask']):
        raise ValueError('Structural stop already breached by closing quote')
    action=mt5.ORDER_TYPE_BUY if side=='BUY' else mt5.ORDER_TYPE_SELL
    loss=mt5.order_calc_profit(action,symbol,1.,entry,sl)
    if type(loss) not in (int,float) or not isfinite(loss) or loss>=0:
        raise ValueError('Broker SL loss calculation unavailable')
    if _account(mt5)!=identity or account_view()!=equity or _valuation_spec(mt5,symbol)!=spec or quote()!=q:
        raise ValueError('Account, equity, specification or quote changed during read')
    nonce=token_hex(32) if account_nonce is None else account_nonce
    if not isinstance(nonce,str) or len(nonce)!=64 or any(c not in '0123456789abcdef' for c in nonce):
        raise ValueError('Local random account nonce required')
    snapshot=dict(account_token=sha256(nonce.encode()+_encode(identity)).hexdigest(),mode='DEMO',symbol=symbol,
        **q,volume_min=spec['volume_min'],volume_max=spec['volume_max'],volume_step=spec['volume_step'],
        broker_loss_one_lot=-loss,spec_token=sha256(_encode(spec)).hexdigest())
    draft=prepare(snapshot=snapshot,side=side,sweep_extreme=sweep_extreme,buffer=buffer,target=target,
                  lots=lots,guards=deepcopy(guards),now_msc=now_msc)
    return dict(status='MT5_READ_ONLY_DEMO_DRAFT',draft=draft,account_nonce=nonce,
        snapshot_origin='CALLER_SUPPLIED_MT5_ADAPTER_NOT_CRYPTOGRAPHIC_AUTHENTICATION',
        stops_margin_and_session_checked=False,execution_allowed=False)
