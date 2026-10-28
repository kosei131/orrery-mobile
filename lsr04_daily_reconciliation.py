"""Account-currency daily balance reconciliation; research only.

The equity-minus-balance bridge is diagnostic, not an independent validation
of floating PnL, credit, blocked funds or broker-specific accounting.
"""
from decimal import Decimal
from math import isfinite


def amount(value):
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError("Finite account amount required")
    return Decimal(str(value))


def reconcile_day(*, opening_balance, opening_equity, closing_balance,
                  closing_equity, trade_net, external_cash_net,
                  history_complete, baseline_verified, tolerance=.01):
    if type(history_complete) is not bool or type(baseline_verified) is not bool:
        raise ValueError("Explicit verification flags required")
    ob, oe, cb, ce, trade, cash, tol = map(amount, (
        opening_balance, opening_equity, closing_balance, closing_equity,
        trade_net, external_cash_net, tolerance))
    if min(ob, oe, cb, ce) <= 0 or not 0 <= tol <= Decimal('.01'):
        raise ValueError("Invalid balances/equities or excessive tolerance")
    residual = cb - ob - trade - cash
    matched = abs(residual) <= tol
    verified = history_complete and baseline_verified and matched
    return dict(status="BALANCE_RECONCILED_RESEARCH" if verified else "BLOCKED_DAILY_RECONCILIATION",
                balance_reconciled=verified, equity_components_verified=False,
                balance_residual=float(residual), balance_change=float(cb-ob),
                trade_net=float(trade), external_cash_net=float(cash),
                equity_change=float(ce-oe),
                equity_change_excluding_external_cash=float(ce-oe-cash),
                nonbalance_equity_component_change=float((ce-cb)-(oe-ob)),
                execution_allowed=False,
                caveat="Balance match is conditional on external baseline/history verification. Equity components are not independently reconciled.")
