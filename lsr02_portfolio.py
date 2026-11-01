"""Single-symbol hypothetical account simulations. No execution/lot APIs."""
from lsr02_exits import finite
from lsr02_study import study, POLICIES


def _account(source, policy, *, initial_equity, risk_fraction, loss_budget_usd, loss_stop):
    """Internal: source must be produced by study with risk=1, fixed fee=0."""
    balance = peak = initial_equity
    floor = initial_equity-loss_budget_usd
    dd = dd_fraction = 0
    streak = max_streak = 0
    halted = None
    active = None
    trades, decisions, ledger = [], [], []
    cost_r = source['round_trip_cost_usd']
    fee = source['portfolio_per_exit_cost_usd']

    def settle(until):
        nonlocal balance, peak, dd, dd_fraction, streak, max_streak, halted, active
        if active is None:
            return
        fills = active['outcome']['fills']
        while active['next_fill'] < len(fills):
            f = fills[active['next_fill']]
            if f['at'] > until:
                break
            gross = f['gross_pnl']*active['risk_usd']
            cost = cost_r*active['risk_usd']*f['fraction']+fee
            net = gross-cost
            balance += net
            if not all(finite(v) for v in (gross, cost, balance)):
                raise ValueError('Unrepresentable accounting result')
            active['net_usd'] += net
            active['next_fill'] += 1
            active['remaining_fraction'] -= f['fraction']
            peak = max(peak, balance)
            dd = max(dd, peak-balance)
            dd_fraction = max(dd_fraction, (peak-balance)/peak)
            ledger.append(dict(at=f['at'], id=active['id'], reason=f['reason'],
                               gross_usd=gross, cost_usd=cost, net_usd=net,
                               balance_usd=balance))
            if balance <= floor:
                halted = halted or 'LOSS_BUDGET_REACHED'
            if balance <= 0:
                halted = 'INSOLVENT'
        if active['next_fill'] == len(fills) and active['outcome']['status'] == 'CLOSED':
            net = active['net_usd']
            streak = streak+1 if net < 0 else (0 if net > 0 else streak)
            max_streak = max(max_streak, streak)
            trades.append(dict(id=active['id'], entry_at=active['entry_at'],
                               closed_at=fills[-1]['at'], risk_usd=active['risk_usd'],
                               net_usd=net, net_r=net/active['risk_usd']))
            if streak >= loss_stop:
                halted = halted or 'CONSECUTIVE_LOSS_STOP'
            active = None

    for c in source['candidates']:
        if c['entry_at'] is None:
            continue
        at = c['entry_at']
        settle(at)  # Only fills observable by this close may affect sizing.
        outcome = c['policies'][policy]
        reason = halted
        risk = balance*risk_fraction
        partial = policy.endswith('_partial')
        expected_cost = risk*cost_r+fee*(2 if partial else 1)
        stop_loss = risk+expected_cost
        distance = abs(c['entry']-c['stop'])
        target_r = 2.6 if policy.startswith('B_') else 2.6*c['sweep_range']/distance
        reward_r = (source['partial_fraction']*source['partial_r']+
                    (1-source['partial_fraction'])*target_r) if partial else target_r
        net_rr = (risk*reward_r-expected_cost)/stop_loss if stop_loss > 0 else None
        if reason is None:
            if active is not None:
                reason = 'POSITION_ALREADY_OPEN'
            elif outcome['status'] == 'SKIP':
                reason = outcome['reason']
            elif net_rr is None or not finite(net_rr) or net_rr < 2:
                reason = 'NET_RR_BELOW_2'
            elif stop_loss >= balance-floor:
                reason = 'INSUFFICIENT_LOSS_BUDGET'
        decisions.append(dict(id=c['id'], at=at,
                              status='SKIP' if reason else 'HYPOTHETICAL_ENTRY',
                              reason=reason, risk_usd=risk,
                              planned_stop_loss_usd=stop_loss, net_rr=net_rr))
        if reason is not None:
            continue
        active = dict(id=c['id'], entry_at=at, risk_usd=risk, outcome=outcome,
                      next_fill=0, net_usd=0, remaining_fraction=1)
    settle(float('inf'))  # Source was already limited to caller's as_of.
    wins = [t for t in trades if t['net_usd'] > 0]
    losses = [t for t in trades if t['net_usd'] < 0]
    profit = sum(t['net_usd'] for t in wins)
    loss = -sum(t['net_usd'] for t in losses)
    n = len(trades)
    return dict(policy=policy, decisions=decisions, fills=ledger, closed_trades=trades,
                ending_realized_balance_usd=balance, realized_net_usd=balance-initial_equity,
                closed_count=n, open_count=int(active is not None),
                open_position=None if active is None else {
                    k: active[k] for k in ('id', 'entry_at', 'risk_usd', 'net_usd', 'remaining_fraction')},
                win_rate=len(wins)/n if n else None,
                expectancy_r=sum(t['net_r'] for t in trades)/n if n else None,
                profit_factor=profit/loss if loss else None,
                max_realized_drawdown_usd=dd, max_realized_drawdown_fraction=dd_fraction,
                max_consecutive_losses=max_streak, current_consecutive_losses=streak,
                halted_reason=halted, execution_allowed=False)


def portfolio(symbol, h4, m15, m5, *, initial_equity, risk_fraction,
              loss_budget_usd, loss_stop, round_trip_cost_r, per_exit_cost_usd,
              **study_settings):
    """Independent account per policy, one open position each; fixed risk %.

    Costs scale linearly with planned risk plus fixed per-exit USD fee.
    This is a research assumption, not broker contract/fee verification.
    """
    if (not all(finite(v) for v in (initial_equity, risk_fraction, loss_budget_usd,
                                   round_trip_cost_r, per_exit_cost_usd))
            or initial_equity <= 0 or not .0025 <= risk_fraction <= .005
            or not 0 < loss_budget_usd < initial_equity
            or min(round_trip_cost_r, per_exit_cost_usd) < 0
            or type(loss_stop) is not int or loss_stop <= 0):
        raise ValueError('Explicit valid hypothetical account rules required')
    source = study(symbol, h4, m15, m5, risk_usd=1,
                   round_trip_cost_usd=round_trip_cost_r, per_exit_cost_usd=0,
                   **study_settings)
    source['portfolio_per_exit_cost_usd'] = per_exit_cost_usd
    return dict(status='HYPOTHETICAL_SINGLE_SYMBOL_ACCOUNTS', symbol=symbol,
                source='CALLER_PROVIDED_UNVERIFIED', execution_allowed=False,
                guard_status='NEWS_SPREAD_BROKER_ACCOUNT_RULES_UNVERIFIED',
                account_rules=dict(initial_equity=initial_equity, risk_fraction=risk_fraction,
                                   loss_budget_usd=loss_budget_usd, loss_stop=loss_stop,
                                   round_trip_cost_r=round_trip_cost_r,
                                   per_exit_cost_usd=per_exit_cost_usd),
                not_entered=source['not_entered'],
                accounts={p: _account(source, p, initial_equity=initial_equity,
                          risk_fraction=risk_fraction, loss_budget_usd=loss_budget_usd,
                          loss_stop=loss_stop) for p in POLICIES})
