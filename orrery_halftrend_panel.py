# SPDX-License-Identifier: GPL-3.0-only
"""Pinned archived study presentation, separate from the displayed chart feed."""
import json
from hashlib import sha256
from pathlib import Path
from orrery_tradingview_window_replay import _summary

GROUPS = ('LSR02', 'VHF03', 'HALFTREND_ALIGNED', 'HALFTREND_OPPOSED', 'HALFTREND_NOT_READY')


def load_panel(path, expected_sha256):
    with Path(path).open('rb') as stream:
        raw = stream.read(8*1024*1024+1)
    if len(raw)>8*1024*1024 or sha256(raw).hexdigest()!=expected_sha256:
        raise ValueError('Archived study size/hash mismatch')
    def reject(value):
        raise ValueError('Non-finite JSON is not a research result')
    r = json.loads(raw, parse_constant=reject)
    if r.get('status')!='HALFTREND_STATE_COHORT_GROSS_REFERENCE_ONLY':
        raise ValueError('Unsupported archived study')
    for key in ('execution_allowed', 'halftrend_filter_adopted', 'reversal04_compared',
                'independent_holdout', 'bid_ask_costs_verified', 'account_risk_controls_applied',
                'tradingview_indicator_parity_verified'):
        if r.get(key) is not False:
            raise ValueError('Research scope is missing or incompatible: '+key)
    if r.get('actual_profit_usd') is not None or r.get('halftrend_cohort_compared') is not True:
        raise ValueError('Gross cohort study required')
    pin = r.get('zip_sha256')
    if not isinstance(pin,str) or len(pin)!=64 or any(c not in '0123456789abcdef' for c in pin):
        raise ValueError('Source ZIP pin required')
    period = r['common_range']
    rows = r['candidates']
    if any(row.get('halftrend_group') not in GROUPS[2:] for row in rows):
        raise ValueError('Unclassified candidate')
    groups = dict(LSR02=rows, VHF03=[row for row in rows if row['vhf_group']=='VHF_PASS'])
    groups.update({g:[row for row in rows if row['halftrend_group']==g] for g in GROUPS[2:]})
    summaries = {g:_summary(v) for g,v in groups.items()}
    if summaries!=r['summaries']:
        raise ValueError('Archived candidate/summary mismatch')
    # Deliberately omit per-candidate plans and any chart overlay or account values.
    return dict(status='ARCHIVED_TRADINGVIEW_STUDY', report_sha256=expected_sha256,
                zip_sha256=pin, common_range=period, summaries=summaries,
                execution_allowed=False, actual_profit_usd=None)
