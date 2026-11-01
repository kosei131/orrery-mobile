"""Pinned local DEMO identity context; no credentials, login or order sending."""
import os
from hashlib import sha256
from pathlib import Path
from secrets import token_hex
from time import time_ns
from lsr03_mt5_pilot import _account
from lsr04_tick_archive import _encode, _decode, _pin
from lsr04_demo_order_check import inspect_order
from lsr04_demo_claims import claim


def _token(identity,nonce):
    return sha256(nonce.encode()+_encode(identity)).hexdigest()


def create_context(mt5,path):
    """Explicit one-time create; preserve the returned SHA separately."""
    identity=_account(mt5);nonce=token_hex(32)
    context=dict(schema_version=1,mode='DEMO',nonce=nonce,
        account_token=_token(identity,nonce),execution_allowed=False)
    if _account(mt5)!=identity:raise ValueError('Account changed while creating context')
    raw=_encode(context)
    fd=os.open(Path(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return dict(status='DEMO_ACCOUNT_CONTEXT_CREATED',context_sha256=sha256(raw).hexdigest(),
        account_token=context['account_token'],execution_allowed=False)


def _load_context(mt5,path,expected_sha256):
    _pin(expected_sha256);p=Path(path)
    if p.is_symlink() or not p.is_file():raise ValueError('Existing regular account context required')
    with p.open('rb') as stream:raw=stream.read(4097)
    if len(raw)>4096 or sha256(raw).hexdigest()!=expected_sha256:
        raise ValueError('Account context pin or size mismatch')
    c=_decode(raw)
    if (not isinstance(c,dict) or set(c)!={'schema_version','mode','nonce','account_token','execution_allowed'}
            or type(c['schema_version']) is not int or c['schema_version']!=1
            or c['mode']!='DEMO' or c['execution_allowed'] is not False):
        raise ValueError('Unsupported account context')
    _pin(c['nonce']);_pin(c['account_token'])
    if _token(_account(mt5),c['nonce'])!=c['account_token']:
        raise ValueError('Current DEMO account differs from saved context')
    return c


def inspect_bound(mt5, *, context_path, expected_context_sha256, clock_msc=None, **draft_args):
    """Use one stable nonce before/after check. Never auto-replace lost context."""
    if 'account_nonce' in draft_args:raise ValueError('Use the persisted context nonce only')
    clock=clock_msc if clock_msc is not None else lambda:time_ns()//1_000_000
    context=_load_context(mt5,context_path,expected_context_sha256)
    result=inspect_order(mt5,clock_msc=clock,account_nonce=context['nonce'],**draft_args)
    if (_load_context(mt5,context_path,expected_context_sha256)!=context
            or result['preflight']['draft_result']['draft']['snapshot']['account_token']!=context['account_token']):
        raise ValueError('Account context changed during bound check')
    completed=clock()
    if type(completed) is not int or not result['checked_at_msc']<=completed<=result['expires_msc']:
        raise ValueError('Account-bound check expired or clock reversed')
    # Persisted nonce stays in the local context file, not in exported review reports.
    result['preflight']['draft_result'].pop('account_nonce')
    return dict(result,account_context_sha256=expected_context_sha256,checked_at_msc=completed)


def check_and_claim(mt5, *, ledger_path, candidate_id, context_path,
                    expected_context_sha256, clock_msc=None, **draft_args):
    """Review + local reservation only. Broker-side idempotency is not implemented."""
    clock=clock_msc if clock_msc is not None else lambda:time_ns()//1_000_000
    report=inspect_bound(mt5,context_path=context_path,expected_context_sha256=expected_context_sha256,
                         clock_msc=clock,**draft_args)
    pin=sha256(_encode(report)).hexdigest()
    reservation=claim(ledger_path,candidate_id=candidate_id,checked_report=report,
                      expected_report_sha256=pin,now_msc=clock())
    return dict(status='DEMO_CHECK_AND_LOCAL_CLAIM_ONLY',checked_report=report,
                reservation=reservation,report_sha256=pin,execution_allowed=False)
