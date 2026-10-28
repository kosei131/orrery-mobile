"""Read-only MT5 DEMO broker-side stop-loss valuation for research.

Calls only account_info, symbol_info, and order_calc_profit (calculation, not
order placement). Does not send orders or authorize trading.
"""
from math import isfinite
from lsr04_broker_sizing import size_from_broker_quote

def demo_stop_sizing(mt5,*,symbol,side,entry_price,stop_price,
                     risk_fraction=.005,existing_risk=0):
    if symbol not in ("XAUUSD","USDJPY") or side not in ("BUY","SELL"):
        raise ValueError("Unsupported symbol/side")
    if any(type(x) not in (int,float) or not isfinite(x) or x<=0 for x in (entry_price,stop_price)):
        raise ValueError("Invalid pricing")
    if not (stop_price<entry_price if side=="BUY" else stop_price>entry_price):
        raise ValueError("Stop must be adverse to entry")
    account=mt5.account_info()
    if account is None or getattr(mt5,"ACCOUNT_TRADE_MODE_DEMO",None) is None or account.trade_mode!=mt5.ACCOUNT_TRADE_MODE_DEMO:
        raise ValueError("Broker-reported demo account required")
    info=mt5.symbol_info(symbol)
    if info is None:
        raise ValueError("Broker symbol specification unavailable")
    currency=getattr(account,"currency",None)
    if currency not in ("USD","JPY"):
        raise ValueError("Unsupported account currency")
    action=mt5.ORDER_TYPE_BUY if side=="BUY" else mt5.ORDER_TYPE_SELL
    loss=mt5.order_calc_profit(action,symbol,1.0,entry_price,stop_price)
    if loss is None or type(loss) not in (int,float) or not isfinite(loss) or loss>=0:
        raise ValueError("Broker calculation absent or not a loss")
    result=size_from_broker_quote(account_currency=currency,
        equity=float(account.equity),risk_fraction=risk_fraction,
        broker_loss_one_lot=float(loss),volume_min=float(info.volume_min),
        volume_max=float(info.volume_max),volume_step=float(info.volume_step),
        max_portfolio_risk_currency=existing_risk)
    return dict(result,broker_one_lot_stop_loss=loss,symbol=symbol,
                verified_demo_mode=True,execution_allowed=False,
                caveat="Cost/commission, stop slippage, margin and executable price checks remain separate.")
