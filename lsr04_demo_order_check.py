"""DEMO order_check only. Never sends orders or grants execution permission."""
from copy import deepcopy
from math import isfinite
from time import time_ns
from lsr04_demo_preflight import review


def inspect_order(mt5, *, clock_msc=None, **draft_args):
    """Rebuild and revalidate around one broker check; refuse partial fills.

    clock_msc is injectable for deterministic tests, not caller authorization.
    No retry, fallback fill policy, terminal initialization or settings changes.
    """
    clock=clock_msc if clock_msc is not None else lambda:time_ns()//1_000_000
    started=clock()
    if type(started) is not int:raise ValueError('Integer wall clock required')
    before=review(mt5,now_msc=started,**draft_args)
    draft=before['draft_result']['draft'];symbol=draft['snapshot']['symbol']
    def filling_state():
        s=mt5.symbol_info(symbol)
        mode=getattr(s,'trade_exemode',None);flags=getattr(s,'filling_mode',None)
        if type(mode) is not int or mode not in (0,1,2,3) or type(flags) is not int or not 0<=flags<=7:
            raise ValueError('Execution and filling modes unavailable')
        # Request/Instant permit FOK regardless of flags; Market/Exchange need bit 1.
        if mode in (2,3) and not flags & 1:raise ValueError('FOK unavailable; partial-fill fallback disabled')
        return (mode,flags)
    modes=filling_state()
    request=dict(action=mt5.TRADE_ACTION_DEAL,symbol=symbol,volume=draft['lots'],
        type=mt5.ORDER_TYPE_BUY if draft['side']=='BUY' else mt5.ORDER_TYPE_SELL,
        sl=draft['stop'],tp=draft['target'],deviation=0,type_filling=mt5.ORDER_FILLING_FOK,
        type_time=mt5.ORDER_TIME_GTC,magic=260405,comment='ORRERY_DEMO_CHECK',
        order=0,position=0,position_by=0,stoplimit=0.,expiration=0)
    if modes[0]!=2:request['price']=draft['entry']
    # Market Execution does not require a request price; risk still uses quote entry.
    result=mt5.order_check(deepcopy(request))
    if result is None:raise ValueError('Broker order check unavailable')
    retcode=getattr(result,'retcode',None)
    if type(retcode) is not int or retcode!=0:raise ValueError('Broker order check rejected or unknown')
    echo=getattr(result,'request',None)
    if echo is None or any(getattr(echo,k,None)!=v for k,v in request.items()):
        raise ValueError('Broker checked request differs from draft')
    if modes[0]==2 and getattr(echo,'price',None)!=0:
        raise ValueError('Unexpected Market Execution request price')
    metrics={k:getattr(result,k,None) for k in ('balance','equity','profit','margin','margin_free','margin_level')}
    if any(type(v) not in (int,float) or not isfinite(v) for v in metrics.values()):
        raise ValueError('Broker check financial result incomplete')
    if (metrics['equity']<=0 or metrics['margin']<=0 or metrics['margin_level']<=0
            or metrics['margin_free']<draft['guards']['cost']):
        raise ValueError('Broker check financial buffer insufficient')
    finished=clock()
    if type(finished) is not int or finished<started:raise ValueError('Wall clock moved backwards')
    args=dict(draft_args,account_nonce=before['draft_result']['account_nonce'])
    after=review(mt5,now_msc=finished,**args)
    if before!=after or filling_state()!=modes:
        raise ValueError('Broker context changed during order check')
    completed=clock()
    if type(completed) is not int or not finished<=completed<=draft['expires_msc']:
        raise ValueError('Quote expired or clock reversed during final review')
    return dict(status='DEMO_ORDER_CHECKED_NOT_ORDER_AUTHORIZATION',preflight=before,
        request=request,check_metrics=metrics,check_retcode=retcode,checked_at_msc=completed,
        expires_msc=draft['expires_msc'],fill_policy='FOK_ONLY',
        broker_session_verified=False,order_check_performed=True,
        duplicate_order_protection_verified=False,execution_allowed=False)
