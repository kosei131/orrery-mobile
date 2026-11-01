"""Research-only broker-calibrated PnL and maximum lots estimator.

Never infer XAUUSD/USDJPY contract value from a symbol string. The caller must
supply verified MT5 order_calc_profit responses in account currency. This
module does not connect to MT5, submit orders or approve live trading.
"""
from math import floor,isfinite

def _positive(x,name):
    if type(x) not in (int,float) or not isfinite(x) or x<=0:
        raise ValueError(name+" must be finite and positive")

def size_from_broker_quote(*,account_currency,equity,risk_fraction,
                           broker_loss_one_lot,volume_min,volume_max,volume_step,
                           max_portfolio_risk_currency=0):
    if account_currency not in ("USD","JPY"):
        raise ValueError("Explicit account currency required")
    for name,value in (("equity",equity),("risk_fraction",risk_fraction),
                       ("volume_min",volume_min),("volume_max",volume_max),
                       ("volume_step",volume_step)):
        _positive(value,name)
    if not 0<risk_fraction<=.01 or volume_max<volume_min or volume_step>volume_max:
        raise ValueError("Invalid research risk or lot bounds")
    if type(broker_loss_one_lot) not in (int,float) or not isfinite(broker_loss_one_lot) or broker_loss_one_lot>=0:
        raise ValueError("Expected negative account-currency loss for exactly one lot")
    if type(max_portfolio_risk_currency) not in (int,float) or not isfinite(max_portfolio_risk_currency) or max_portfolio_risk_currency<0:
        raise ValueError("Invalid existing risk")
    budget=equity*risk_fraction-max_portfolio_risk_currency
    if budget<=0:
        return dict(status="NO_CAPACITY",lots=0.,execution_allowed=False)
    raw=min(volume_max,budget/(-broker_loss_one_lot))
    # MT5 volume_min + n*volume_step lattice, never round upwards.
    n=floor((raw-volume_min)/volume_step+1e-10)
    if n<0:
        return dict(status="BELOW_MIN_LOT",lots=0.,execution_allowed=False)
    lots=round(volume_min+n*volume_step,8)
    if -broker_loss_one_lot*lots>budget+1e-7:
        raise AssertionError("Sizing exceeded risk budget")
    return dict(status="RESEARCH_SIZE",lots=lots,
        risk_budget=round(budget,6),
        modeled_stop_loss=round(broker_loss_one_lot*lots,6),
        currency=account_currency,execution_allowed=False,
        limitations="Requires broker-verified order_calc_profit and separate commission, swaps, slippage, stop gap and margin checks.")
