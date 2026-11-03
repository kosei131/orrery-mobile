# SPDX-License-Identifier: GPL-3.0-only
"""Replay explicitly supplied ZIPs with the frozen pilot, then present a subset."""
from hashlib import sha256
import json
from pathlib import Path
from orrery_halftrend_holdout_batch import review, _read
from orrery_prospective_status import PLAN, PLAN_SHA256


def replay_panel(inputs, plan_raw, *, plan_sha256, now=None):
    r = review(inputs, plan_raw, plan_sha256=plan_sha256, now=now)
    # Deliberately omit individual trade plans and local paths from the HTTP API.
    keys = ('plan_sha256', 'batch_code_sha256', 'observed_at_utc', 'sorted_zip_sha256',
            'discovery_summaries', 'summaries', 'unsubmitted_common_span_gaps',
            'submitted_common_span_seconds', 'planned_period_seconds', 'partial_period',
            'complete_session_coverage_verified', 'boundary_state_reset',
            'continuous_strategy_equivalence_verified', 'independent_holdout_verified',
            'halftrend_filter_adopted', 'reversal04_compared', 'six_month_backtest_complete',
            'account_risk_controls_applied', 'net_expectancy_r', 'account_return_pct',
            'account_max_dd_usd', 'actual_profit_usd', 'verdict', 'execution_allowed')
    panel = {k:r[k] for k in keys}
    panel['status'] = 'REPLAYED_PROSPECTIVE_ZIP_PANEL'
    panel['segments'] = [dict(zip_sha256=v['input_zip_sha256'],
                              common_range=v['prospective_study']['common_range']) for v in r['reports']]
    return panel


def load_panel(manifest_path, manifest_sha256):
    raw = _read(manifest_path, 1024*1024)
    if sha256(raw).hexdigest() != manifest_sha256:
        raise ValueError('Prospective manifest hash mismatch')
    manifest = json.loads(raw)
    if not isinstance(manifest, list) or not 1 <= len(manifest) <= 8:
        raise ValueError('One to eight explicit ZIP inputs required')
    for item in manifest:
        if (not isinstance(item, dict) or set(item) != {'zip_path','zip_sha256'}
                or not isinstance(item['zip_path'], str) or not item['zip_path']):
            raise ValueError('Exact ZIP manifest fields required')
    # Same cwd-relative path convention as the existing batch CLI. No extraction,
    # network, directory scanning or automatic discovery of user files.
    inputs = []; budget = 32*1024*1024
    for item in manifest:
        data = _read(item['zip_path'], min(16*1024*1024, budget))
        budget -= len(data)
        inputs.append(dict(raw=data, zip_sha256=item['zip_sha256']))
    panel = replay_panel(inputs, _read(PLAN,1024*1024), plan_sha256=PLAN_SHA256)
    panel['manifest_sha256'] = manifest_sha256
    return panel
