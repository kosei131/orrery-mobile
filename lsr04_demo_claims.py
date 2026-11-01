"""Persistent local candidate claims only; no broker orders or retry permission."""
import os
import sqlite3
from hashlib import sha256
from pathlib import Path
from lsr04_tick_archive import _encode, _pin


def initialize(path, *, account_token):
    """Explicit new ledger. Never silently create a replacement on claim."""
    _pin(account_token)
    p=Path(path)
    fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    db=sqlite3.connect(p)
    try:
        db.execute('CREATE TABLE context (version INTEGER NOT NULL, account_token TEXT NOT NULL)')
        db.execute('INSERT INTO context VALUES (1,?)',(account_token,))
        db.execute('CREATE TABLE claims (candidate_id TEXT PRIMARY KEY, report_sha256 TEXT NOT NULL, claimed_at_msc INTEGER NOT NULL)')
        db.commit()
    finally:db.close()
    return dict(status='DEMO_CLAIM_LEDGER_CREATED',execution_allowed=False)


def claim(path, *, candidate_id, checked_report, expected_report_sha256, now_msc):
    """Serialize contenders by candidate ID across quotes/sides/strategy versions.

    Pins detect accidental changes, not adapter or account authenticity.
    Reservations never auto-release, including after expiry or unknown outcomes.
    """
    _pin(expected_report_sha256)
    if (not isinstance(candidate_id,str) or not candidate_id.strip() or len(candidate_id)>200
            or any(ord(c)<32 for c in candidate_id)):
        raise ValueError('Stable bounded nonsecret candidate ID required')
    raw=_encode(checked_report)
    if sha256(raw).hexdigest()!=expected_report_sha256:raise ValueError('Checked report pin mismatch')
    r=checked_report
    if (r.get('status')!='DEMO_ORDER_CHECKED_NOT_ORDER_AUTHORIZATION'
            or r.get('execution_allowed') is not False or r.get('order_check_performed') is not True
            or type(r.get('check_retcode')) is not int or r['check_retcode']!=0
            or r.get('fill_policy')!='FOK_ONLY'):
        raise ValueError('Successful non-executable DEMO check required')
    d=r['preflight']['draft_result']['draft'];s=d['snapshot'];_pin(s['account_token'])
    if (s.get('mode')!='DEMO' or d.get('execution_allowed') is not False
            or type(now_msc) is not int or type(r.get('checked_at_msc')) is not int
            or type(r.get('expires_msc')) is not int or r['expires_msc']!=d['expires_msc']
            or not 0<=r['checked_at_msc']<=now_msc<=r['expires_msc']):
        raise ValueError('Fresh DEMO checked report required')
    p=Path(path)
    if p.is_symlink() or not p.is_file():raise ValueError('Existing regular claim ledger required')
    try:
        # mode=rw is essential: a lost/deleted ledger must never be recreated.
        db=sqlite3.connect(p.absolute().as_uri()+'?mode=rw',uri=True,timeout=2.)
        try:
            db.execute('PRAGMA synchronous=FULL')
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT version,account_token FROM context').fetchall()!=[(1,s['account_token'])]:
                raise ValueError('Claim ledger account or schema mismatch')
            if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise ValueError('Corrupt claim ledger')
            db.execute('INSERT INTO claims VALUES (?,?,?)',(candidate_id,expected_report_sha256,now_msc))
            db.commit()
        finally:db.close()
    except sqlite3.IntegrityError as exc:raise ValueError('Candidate already claimed; automatic retry forbidden') from exc
    except sqlite3.Error as exc:raise ValueError('Claim ledger unavailable; no automatic replacement') from exc
    return dict(status='DEMO_CANDIDATE_CLAIMED_NOT_ORDER_AUTHORIZATION',candidate_id=candidate_id,
        report_sha256=expected_report_sha256,execution_allowed=False,
        broker_order_sent=False,broker_idempotency_verified=False)
