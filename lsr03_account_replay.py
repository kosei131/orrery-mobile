"""Single-symbol, one-position USD account research replay.

Requires caller-supplied historical broker PnL callback; no MT5/order calls.
Optional historical carry/boundary evidence; no margin or real-market proof.
Full modeled round-trip commission is charged at entry, deliberately explicit.
"""
from datetime import datetime, timezone, timedelta
from math import isfinite
from lsr04_broker_sizing import size_from_broker_quote
from lsr04_account_gate import review, _amount
from lsr04_tick_fills import replay_exit
from lsr02_risk_plan import performance


def _num(value, positive=False):
    if type(value) not in (int,float) or not isfinite(value) or (positive and value<=0):
        raise ValueError('Finite account replay input required')
    return float(value)


def replay_account(quotes, candidates, *, symbol, volume_min, volume_max, volume_step,
                   pnl_quote, round_trip_cost_per_lot_usd, cost_source,
                   slippage, initial_equity=3000, risk_fraction=.0025,
                   daily_boundary_utc_hour=10, max_quotes=1000000, cancellations=(),
                   carry_quote=None, carry_source=None, boundary_quote_max_age_msc=0):
    if symbol not in ('XAUUSD','USDJPY') or not callable(pnl_quote):
        raise ValueError('Explicit single symbol and historical USD PnL callback required')
    if not isinstance(cost_source,str) or not cost_source.strip():raise ValueError('Cost provenance required')
    initial=_num(initial_equity,True)
    if initial!=3000:raise ValueError('Requested account starts at $3000')
    if risk_fraction!=.0025 or type(risk_fraction) not in (int,float):raise ValueError('Fixed 0.25% research risk')
    fee_rate=_num(round_trip_cost_per_lot_usd);slip=_num(slippage)
    if min(fee_rate,slip)<0:raise ValueError('Nonnegative explicit fees/slippage required')
    if type(daily_boundary_utc_hour) is not int or not 0<=daily_boundary_utc_hour<24:
        raise ValueError('Explicit daily UTC boundary required')
    if carry_quote is not None and (not callable(carry_quote) or not isinstance(carry_source,str) or not carry_source.strip()):
        raise ValueError('Historical cumulative USD carry callback/source required')
    if carry_quote is None and carry_source is not None:
        raise ValueError('Carry source without callback is not valuation evidence')
    if type(boundary_quote_max_age_msc) is not int or not 0<=boundary_quote_max_age_msc<=10000:
        raise ValueError('Explicit 0-10000ms boundary quote age required')
    if type(max_quotes) is not int or not 1<=max_quotes<=10000000:raise ValueError('Bounded quote budget required')
    # Validate the existing broker volume/sizing contract even with no candidates.
    size_from_broker_quote(account_currency='USD',equity=initial,risk_fraction=risk_fraction,
        broker_loss_one_lot=-1,volume_min=volume_min,volume_max=volume_max,volume_step=volume_step)
    if not isinstance(candidates,list) or len(candidates)>10000:raise ValueError('Bounded confirmed candidate list required')
    plans=[];ids=set();last_known=None
    for c in candidates:
        if not isinstance(c,dict) or set(c)!={'id','symbol','side','known_at_msc','eligible_after_msc','expires_at_msc','stop','target'}:
            raise ValueError('Only as-of entry plans accepted; no future outcome fields')
        if not isinstance(c['id'],str) or not c['id'] or c['id'] in ids or c['symbol']!=symbol or c['side'] not in ('BUY','SELL'):
            raise ValueError('Unique same-symbol candidates required')
        ids.add(c['id'])
        for k in ('known_at_msc','eligible_after_msc','expires_at_msc'):
            if type(c[k]) is not int or c[k]<0:raise ValueError('Integer candidate clock required')
        if not c['known_at_msc']<c['eligible_after_msc']<c['expires_at_msc'] or (last_known is not None and c['known_at_msc']<last_known):
            raise ValueError('Chronological, strictly post-confirmation plans required')
        _num(c['stop'],True);_num(c['target'],True)
        if not (c['stop']<c['target'] if c['side']=='BUY' else c['target']<c['stop']):raise ValueError('Invalid stop/target order')
        plans.append(dict(c));last_known=c['known_at_msc']
    if not isinstance(cancellations,(list,tuple)) or len(cancellations)>10000:
        raise ValueError('Bounded chronological cancellation events required')
    known_by_id={c['id']:c['known_at_msc'] for c in plans}
    canceled={};previous_cancel=None
    for event in cancellations:
        if not isinstance(event,dict) or set(event)!={'id','known_at_msc'} or event['id'] not in known_by_id:
            raise ValueError('Cancellation must reference a confirmed plan')
        at=event['known_at_msc']
        if type(at) is not int or at<known_by_id[event['id']] or (previous_cancel is not None and at<previous_cancel):
            raise ValueError('Invalid cancellation clock')
        if event['id'] in canceled:raise ValueError('Duplicate cancellation event')
        canceled[event['id']]=at;previous_cancel=at
    balance=equity=peak=initial;max_dd=0.;day=None;day_equity=None
    daily_held=False;streak_held=False;streak=max_streak=0;active=None
    pending=[];cursor=0;previous=None;last_exit=None;count=0
    trades=[];decisions=[];events=[];sessions=[]
    prior_quote=None;total_carry=0.
    epoch=datetime(1970,1,1,tzinfo=timezone.utc)
    def pnl(side,lots,entry,exit_price,at):
        return _num(pnl_quote(symbol,side,lots,entry,exit_price,at))
    def track(at,reason):
        nonlocal peak,max_dd
        _num(balance);_num(equity)
        peak=max(peak,equity);max_dd=max(max_dd,peak-equity)
        if len(events)>=20000:raise ValueError('Account-event output budget exceeded')
        events.append(dict(at_msc=at,reason=reason,balance_usd=balance,equity_usd=equity))
    def accrue(at):
        nonlocal balance,total_carry
        if active is None or carry_quote is None:return
        cumulative=_num(carry_quote(symbol,active['side'],active['lots'],active['entry_at'],at))
        if at==active['carry_at'] and cumulative!=active['carry']:
            raise ValueError('Historical carry changed at the same observation clock')
        delta=float(_amount(cumulative)-_amount(active['carry']))
        balance-=delta;total_carry+=delta
        active['carry']=cumulative;active['carry_at']=at
    def closed_trade(position,price_gross,at,reason):
        carry=position['carry']
        # Existing performance helper requires nonnegative costs. Swap credits
        # are explicit income; neither costs nor credits are silently discarded.
        return dict(id=position['id'],closed_at=at/1000,
            gross_pnl=price_gross+max(0.,-carry),cost=position['fee']+max(0.,carry),
            price_gross_pnl_usd=price_gross,carry_cost_usd=carry,
            initial_risk=position['planned_risk'],lots=position['lots'],
            net_usd=price_gross-position['fee']-carry,
            entry_at_msc=position['entry_at'],exit_reason=reason)
    for q in quotes:
        count+=1
        if count>max_quotes:raise ValueError('Quote budget exceeded; no prefix result')
        if not isinstance(q,dict) or set(q)!={'time_msc','bid','ask'} or type(q['time_msc']) is not int or q['time_msc']<0:
            raise ValueError('Normalized quote required')
        at=q['time_msc'];bid=_num(q['bid'],True);ask=_num(q['ask'],True)
        if bid>ask or (previous is not None and at<previous):raise ValueError('Invalid quote chronology/prices')
        previous=at
        session=(at-daily_boundary_utc_hour*3600000)//86400000
        if day!=session:
            boundary=session*86400000+daily_boundary_utc_hour*3600000
            method='FLAT_CASH_BASELINE';price_clock=None
            if active is not None:
                if carry_quote is None:raise ValueError('Overnight carry callback/source required')
                if session!=day+1:raise ValueError('Missing intervening daily boundary evidence')
                baseline_quote=q if at==boundary else prior_quote
                if baseline_quote is None or not 0<=boundary-baseline_quote['time_msc']<=boundary_quote_max_age_msc:
                    raise ValueError('Missing or stale as-of boundary quote; no future-price substitution')
                accrue(boundary)
                price=baseline_quote['bid'] if active['side']=='BUY' else baseline_quote['ask']
                equity=balance+pnl(active['side'],active['lots'],active['entry_price'],price,boundary)
                _num(equity,True)
                method='EXACT_BOUNDARY_QUOTE' if baseline_quote['time_msc']==boundary else 'LAST_OBSERVED_BEFORE_BOUNDARY'
                price_clock=baseline_quote['time_msc']
                track(boundary,'DAY_BOUNDARY_BEFORE_FILL')
                baseline=equity
            else:baseline=balance
            day=session;day_equity=baseline;daily_held=False
            if len(sessions)>=10000:raise ValueError('Daily snapshot budget exceeded')
            sessions.append(dict(start_msc=boundary,starting_equity_usd=baseline,
                method=method,quote_time_msc=price_clock))
        if active is not None:accrue(at)
        if active is not None:
            outcome=replay_exit([active['entry_quote'],q],side=active['side'],
                entry_after_msc=active['entry_at'],stop_price=active['stop'],target_price=active['target'],slippage=slip)
            if outcome['status']=='CLOSED':
                _num(outcome['exit_price'],True)
                gross=pnl(active['side'],active['lots'],active['entry_price'],outcome['exit_price'],at)
                balance+=gross;equity=balance
                trade=closed_trade(active,gross,at,outcome['exit_reason'])
                net=trade['net_usd'];trades.append(trade)
                streak=streak+1 if net<0 else 0
                max_streak=max(max_streak,streak);streak_held=streak_held or streak>=3
                active=None;last_exit=at;track(at,'CLOSE')
            else:
                mark=bid if active['side']=='BUY' else ask
                equity=balance+pnl(active['side'],active['lots'],active['entry_price'],mark,at)
        else:equity=balance
        # No future equity is used for a daily halt or entry budget.
        if _amount(day_equity)-_amount(equity)>=_amount(day_equity)*_amount(.01):daily_held=True
        peak=max(peak,equity);max_dd=max(max_dd,peak-equity)
        if equity<=0:raise ValueError('Insolvent path requires liquidation model; no completed simulation')
        while cursor<len(plans) and plans[cursor]['known_at_msc']<at:
            pending.append(plans[cursor]);cursor+=1
        waiting=[]
        for c in pending:
            if at<c['eligible_after_msc']:waiting.append(c);continue
            reason=None
            if c['id'] in canceled and canceled[c['id']]<=at:reason='INVALIDATED_BEFORE_FILL'
            elif at>=c['expires_at_msc']:reason='EXPIRED'
            elif active is not None:reason='POSITION_ALREADY_OPEN'
            elif daily_held:reason='LATCHED_DAILY_STOP'
            elif streak_held:reason='LATCHED_THREE_LOSS_STOP'
            elif last_exit is not None and at<=last_exit:reason='SAME_TIMESTAMP_REENTRY'
            entry=ask+slip if c['side']=='BUY' else bid-slip
            if reason is None and not (c['stop']<entry<c['target'] if c['side']=='BUY' else c['target']<entry<c['stop']):reason='INVALID_STRUCTURE'
            if reason is not None:
                decisions.append(dict(id=c['id'],at_msc=at,status='SKIP',reason=reason));continue
            modeled_stop=c['stop']-slip if c['side']=='BUY' else c['stop']+slip
            _num(modeled_stop,True)
            one_lot=pnl(c['side'],1.,entry,modeled_stop,at)
            if one_lot>=0:raise ValueError('Broker stop quote must be adverse')
            sized=size_from_broker_quote(account_currency='USD',equity=equity,risk_fraction=risk_fraction,
                broker_loss_one_lot=one_lot-fee_rate,volume_min=volume_min,
                volume_max=volume_max,volume_step=volume_step)
            lots=sized['lots']
            if lots<=0:
                decisions.append(dict(id=c['id'],at_msc=at,status='SKIP',reason=sized['status']));continue
            fee=fee_rate*lots
            planned=-pnl(c['side'],lots,entry,modeled_stop,at)+fee
            if planned<=0 or planned>equity*risk_fraction+1e-8:
                raise ValueError('Nonlinear broker PnL exceeded sizing budget')
            day_start=epoch+timedelta(milliseconds=session*86400000+daily_boundary_utc_hour*3600000)
            gate=review(day_start_utc=day_start,now_utc=epoch+timedelta(milliseconds=at),
                day_start_equity=day_equity,current_equity=equity,existing_stop_risk=0,
                proposed_stop_risk=planned,consecutive_losses=streak)
            if gate['reasons']:
                decisions.append(dict(id=c['id'],at_msc=at,status='SKIP',reason=';'.join(gate['reasons'])));continue
            balance-=fee
            active=dict(c,lots=lots,entry_quote=dict(q),entry_at=at,entry_price=entry,
                        planned_risk=planned,fee=fee,carry=0.,carry_at=at)
            if carry_quote is not None:
                initial_carry=_num(carry_quote(symbol,c['side'],lots,at,at))
                if initial_carry!=0:raise ValueError('Cumulative carry must start at zero at entry')
            decisions.append(dict(id=c['id'],at_msc=at,status='RESEARCH_ENTRY',lots=lots,planned_risk_usd=planned))
            # Include immediate spread/slippage loss and same-quote SL behavior.
            opening=replay_exit([q],side=c['side'],entry_after_msc=at,stop_price=c['stop'],target_price=c['target'],slippage=slip)
            if opening['status']=='CLOSED':
                _num(opening['exit_price'],True)
                gross=pnl(c['side'],lots,entry,opening['exit_price'],at)
                balance+=gross;equity=balance
                trade=closed_trade(active,gross,at,opening['exit_reason'])
                net=trade['net_usd'];trades.append(trade)
                streak=streak+1 if net<0 else 0;max_streak=max(max_streak,streak)
                streak_held=streak_held or streak>=3;active=None;last_exit=at
            else:equity=balance+pnl(c['side'],lots,entry,bid if c['side']=='BUY' else ask,at)
            track(at,'ENTRY_AND_MARK')
            if _amount(day_equity)-_amount(equity)>=_amount(day_equity)*_amount(.01):daily_held=True
            if equity<=0:raise ValueError('Insolvent entry path requires liquidation model')
        pending=waiting
        prior_quote=dict(q)
    if count==0:raise ValueError('Nonempty quote stream required')
    for c in pending+plans[cursor:]:
        decisions.append(dict(id=c['id'],at_msc=previous,status='NO_ENTRY',reason='NO_ELIGIBLE_QUOTE'))
    # Reuse descriptive realized-trade statistics; do not use its DD/streak
    # convention for account gates (this engine's breakeven resets streak).
    stats=performance(trades,initial_equity=initial)
    selected={k:stats[k] for k in ('trades','wins','losses','breakeven','win_rate','expectancy_r','profit_factor')}
    return dict(status='INTRADAY_SINGLE_SYMBOL_ACCOUNT_RESEARCH' if carry_quote is None else 'SINGLE_SYMBOL_CARRY_ACCOUNT_RESEARCH',symbol=symbol,
        initial_equity_usd=initial,ending_balance_usd=balance,ending_equity_usd=equity,
        balance_change_usd=balance-initial,equity_change_usd=equity-initial,
        closed_trade_net_usd=sum(t['net_usd'] for t in trades),
        max_sampled_equity_drawdown_usd=max_dd,closed_statistics=selected,
        max_consecutive_losses=max_streak,daily_stop_held=daily_held,streak_stop_held=streak_held,
        open_position=None if active is None else {k:active[k] for k in ('id','lots','entry_price','planned_risk','fee','carry')},
        trades=trades,decisions=decisions,account_events=events,cost_source=cost_source,
        daily_snapshots=sessions,carry_cost_usd=total_carry,carry_source=carry_source,
        carry_mode='DISABLED_INTRADAY_ONLY' if carry_quote is None else 'CALLER_CUMULATIVE_USD',
        boundary_quote_max_age_msc=boundary_quote_max_age_msc,
        execution_allowed=False,market_edge_verified=False,six_month_backtest_complete=False,
        limitations='Caller historical USD PnL/fee/carry inputs unverified. Single symbol/one position. Carry requires as-of boundary quote and callback. Full round-trip fee charged at entry. Future carry risk is not reserved in sizing. No margin, multi-symbol or automatic missing-boundary reconstruction. Three-loss latch has no automatic reset.')
