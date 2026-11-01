"""Fail-closed position-lifetime accounting, account-currency PnL, no orders.

INOUT is deliberately unresolved: reversal costs cannot safely be apportioned.
A caller's completeness assertion is evidence supplied externally, not proof
that MT5 returned every deal or that broker fees are fully attributed.
"""
from math import isfinite


def _num(x):
    if type(x) not in (int, float) or not isfinite(x):
        raise ValueError("Finite field required")
    return float(x)


def reconcile(deals, *, entry_in, entry_out, entry_inout,
              open_position_ids=(), history_complete=False):
    if not isinstance(deals, list) or len(deals) > 100000:
        raise ValueError("Bounded deal history required")
    if type(history_complete) is not bool:
        raise ValueError("Explicit completeness assertion required")
    if len({entry_in, entry_out, entry_inout}) != 3:
        raise ValueError("Distinct entry constants required")
    if not isinstance(open_position_ids, (list, tuple, set)) or any(
            type(p) is not int or p <= 0 for p in open_position_ids):
        raise ValueError("Open position identities required")
    groups = {}; seen = set()
    for d in deals:
        pid = getattr(d, "position_id", None)
        if type(pid) is not int or pid <= 0:
            raise ValueError("Missing position identity / unattributed account operation")
        key = (getattr(d, "time_msc", None), getattr(d, "ticket", None))
        if any(type(x) is not int or x < 0 for x in key) or key[1] == 0:
            raise ValueError("Deal ordering provenance required")
        if key[1] in seen:
            raise ValueError("Duplicate deal ticket")
        seen.add(key[1])
        if getattr(d, "entry", None) not in (entry_in, entry_out, entry_inout):
            raise ValueError("Unknown deal entry category (including unsupported OUT_BY)")
        if _num(getattr(d, "volume", None)) <= 0:
            raise ValueError("Positive deal volume required")
        for field in ("profit", "commission", "swap", "fee"):
            _num(getattr(d, field, None))
        groups.setdefault(pid, []).append(d)
    completed = []; unresolved = set(open_position_ids)
    for pid, rows in groups.items():
        rows.sort(key=lambda d: (d.time_msc, d.ticket))
        g = dict(position_id=pid, opened=0., closed=0., net=0.,
                 last_close=None, deal_count=len(rows), has_reversal=False,
                 profit=0., commission=0., swap=0., fee=0.)
        balance = 0.; invalid = False; finished = False
        for d in rows:
            if finished:
                invalid = True  # position identifier reused after full closure
            for field in ("profit", "commission", "swap", "fee"):
                g[field] += getattr(d, field)
            if d.entry == entry_in:
                g["opened"] += d.volume
                balance += d.volume
            elif d.entry == entry_out:
                if d.volume > balance + 1e-9:
                    invalid = True
                balance -= d.volume
                g["closed"] += d.volume
                g["last_close"] = (d.time_msc, d.ticket)
                if abs(balance) <= 1e-9:
                    balance = 0.; finished = True
            else:
                g["has_reversal"] = True
        g["net"] = sum(g[f] for f in ("profit", "commission", "swap", "fee"))
        if not all(isfinite(g[f]) for f in ("profit", "commission", "swap", "fee", "net", "opened", "closed")):
            raise ValueError("Account aggregation overflow")
        if invalid or g["has_reversal"] or pid in unresolved or balance != 0 or g["opened"] <= 0:
            unresolved.add(pid)
        else:
            g["outcome"] = "LOSS" if g["net"] < 0 else "WIN" if g["net"] > 0 else "BREAKEVEN"
            completed.append(g)
    completed.sort(key=lambda g: g["last_close"])
    losses = 0
    for g in reversed(completed):
        if g["net"] < 0:
            losses += 1
        else:
            break  # explicit policy: breakeven resets the streak
    known = history_complete and not unresolved
    return dict(status="GROUPED_HISTORY_RESEARCH" if known else "COMPLETE_HISTORY_REQUIRED",
                completed_positions=len(completed), unresolved_position_ids=sorted(unresolved),
                consecutive_losses=losses if known else None,
                loss_streak_stop=losses >= 3 if known else None,
                positions=completed, execution_allowed=False,
                caveat="Completeness and fee attribution require external verification; PnL is account currency. No equity/day reconciliation.")
