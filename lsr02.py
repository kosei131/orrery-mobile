"""LSR-02 experimental decision gates. No market connection, sizing or order API.
Evidence must be externally computed from closed bars without future data.
READY means eligible for demo review, never permission to send an order.
"""
from math import isfinite

STATES = ('WATCH', 'SWEEP', 'CONFIRM', 'RETEST', 'READY', 'INVALID')
REQUIRED = {
    'SWEEP': ('htf_context', 'sweep_closed'),
    'CONFIRM': ('structure_closed', 'poi_defined'),
    'RETEST': ('poi_retested', 'entry_bar_closed'),
    'READY': ('risk_checked',),
}

def advance(state, evidence):
    if state not in STATES:
        raise ValueError('Unknown state')
    if state == 'INVALID':
        return state
    if evidence.get('invalidated') is True:
        return 'INVALID'
    if state == 'READY':
        return state if evidence.get('risk_checked') is True else 'INVALID'
    target = STATES[STATES.index(state) + 1]
    return target if all(evidence.get(k) is True for k in REQUIRED[target]) else state


def risk_gate(*, equity, risk_fraction, existing_risk, max_total_risk,
              remaining_loss_budget, entry, sl, tp, side, cost,
              consecutive_losses, loss_stop, data_ok=False,
              news_clear=False, spread_ok=False):
    """USD only; dollar risk includes caller-supplied conservative costs.
    Limits must come from verified account rules. Does not calculate lots.
    """
    values = (equity, risk_fraction, existing_risk, max_total_risk,
              remaining_loss_budget, entry, sl, tp, cost)
    if any(type(v) not in (int, float) or not isfinite(v) for v in values):
        return False
    if not (equity > 0 and .0025 <= risk_fraction <= .005 and
            existing_risk >= 0 and max_total_risk > 0 and
            remaining_loss_budget > 0 and cost >= 0 and min(entry, sl, tp) > 0):
        return False
    if type(consecutive_losses) is not int or type(loss_stop) is not int or not 0 <= consecutive_losses < loss_stop:
        return False
    if not all(v is True for v in (data_ok, news_clear, spread_ok)):
        return False
    if not ((side == 'BUY' and sl < entry < tp) or (side == 'SELL' and tp < entry < sl)):
        return False
    risk = equity * risk_fraction
    # Cost is deducted from rewards and added to losses for conservative net RR.
    gross_rr = abs(tp-entry) / abs(entry-sl)
    net_rr = (risk*gross_rr-cost)/(risk+cost)
    total = existing_risk + risk + cost
    return net_rr >= 2 and total <= max_total_risk and total < remaining_loss_budget


def hypothesis_targets(side, entry, sl, measured_range):
    """Separate experimental targets. C deliberately remains undefined."""
    if side not in ('BUY', 'SELL') or any(type(x) not in (int, float) or not isfinite(x) or x <= 0 for x in (entry, sl, measured_range)):
        raise ValueError('Invalid hypothesis input')
    if (side == 'BUY' and sl >= entry) or (side == 'SELL' and sl <= entry):
        raise ValueError('Invalid stop direction')
    sign = 1 if side == 'BUY' else -1
    return {'A_range_2_6': entry+sign*2.6*measured_range,
            'B_gross_rr_2_6': entry+sign*2.6*abs(entry-sl),
            'C_undefined': None}
