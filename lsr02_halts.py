"""Local durable research halt latch. Never stores credentials, prices or account IDs.
Creation is explicit; missing/corrupt stores raise instead of resetting safety state.
"""
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4
from lsr02_sequence import number

SYMBOLS=('XAUUSD','USDJPY')

class HaltStore:
    def __init__(self,path,*,create=False):
        self.path=Path(path)
        if create:
            fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            os.close(fd)
            with closing(sqlite3.connect(self.path)) as db, db:
                db.execute('CREATE TABLE metadata (version INTEGER NOT NULL)')
                db.execute('INSERT INTO metadata VALUES (1)')
                db.execute('CREATE TABLE halts (symbol TEXT PRIMARY KEY, reason TEXT NOT NULL, at REAL NOT NULL, token TEXT NOT NULL)')
        self._read_version()

    def _connect(self):
        # rw refuses to recreate a deleted store. SQLite serializes writes.
        return sqlite3.connect(self.path.resolve().as_uri()+'?mode=rw',uri=True,timeout=5)

    def _read_version(self):
        with closing(self._connect()) as db:
            if db.execute('SELECT version FROM metadata').fetchall()!=[(1,)]:
                raise ValueError('Unknown halt store version')

    def get(self,symbol):
        if symbol not in SYMBOLS:raise ValueError('Unsupported symbol')
        with closing(self._connect()) as db:
            row=db.execute('SELECT reason,at,token FROM halts WHERE symbol=?',(symbol,)).fetchone()
        if row is None:return None
        if row[0]!='REGIME_REVIEW_REQUIRED' or not number(row[1]) or not isinstance(row[2],str) or len(row[2])!=32:
            raise ValueError('Invalid halt record')
        return dict(reason=row[0],at=row[1],token=row[2])

    def halt(self,symbol,at):
        if symbol not in SYMBOLS or not number(at):raise ValueError('Invalid halt')
        token=uuid4().hex
        with closing(self._connect()) as db, db:
            db.execute('INSERT OR REPLACE INTO halts VALUES (?,?,?,?)',(symbol,'REGIME_REVIEW_REQUIRED',at,token))
        return token

    def acknowledge(self,symbol,token):
        """Explicit review acknowledgement only; not called by replay or a scheduler.
        It clears this latch, not other risk gates and never authorizes orders.
        """
        if symbol not in SYMBOLS or not isinstance(token,str):raise ValueError('Invalid acknowledgement')
        with closing(self._connect()) as db, db:
            return db.execute('DELETE FROM halts WHERE symbol=? AND token=?',(symbol,token)).rowcount==1


class DailyRiskHaltStore:
    """Separate account/session latch; deliberately has no acknowledge/clear API.

    Reuses the existing rw-only SQLite connection primitive. Session creation
    is explicit; observations never create/reset missing sessions. No raw
    account identities, credentials, prices or balances are stored.
    """
    _connect = HaltStore._connect
    REASONS = frozenset(('DAILY_DRAWDOWN_STOP', 'LOSS_STREAK_STOP'))

    def __init__(self, path, *, create=False):
        self.path = Path(path)
        if create:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            with closing(self._connect()) as db, db:
                db.execute('CREATE TABLE daily_metadata (version INTEGER NOT NULL)')
                db.execute('INSERT INTO daily_metadata VALUES (1)')
                db.execute('''CREATE TABLE daily_risk_halts (
                    scope TEXT NOT NULL, session REAL NOT NULL,
                    policy TEXT NOT NULL, last_at REAL NOT NULL,
                    reasons TEXT NOT NULL, PRIMARY KEY(scope, session))''')
        with closing(self._connect()) as db:
            self._validate(db)

    def _validate(self, db):
        if db.execute('SELECT version FROM daily_metadata').fetchall() != [(1,)]:
            raise ValueError('Unknown daily halt schema')
        db.execute('SELECT scope,session,policy,last_at,reasons FROM daily_risk_halts LIMIT 0')

    @staticmethod
    def _key(value):
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Opaque SHA-256 scope/policy required')
        return value

    @staticmethod
    def _time(value):
        from datetime import datetime
        if not isinstance(value, datetime) or value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
            raise ValueError('Explicit UTC time required')
        return value.timestamp()

    def initialize_session(self, *, scope, day_start_utc, policy, verified_start=False):
        """Explicit baseline/history review action; never invoked by observation.

        verified_start asserts prior breach history is reviewed, not just that
        a starting equity number exists. Previous records are retained.
        """
        self._key(scope); self._key(policy)
        start = self._time(day_start_utc)
        if verified_start is not True or day_start_utc.microsecond != 0:
            raise ValueError('Verified session start required')
        with closing(self._connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            self._validate(db)
            latest = db.execute('SELECT MAX(session) FROM daily_risk_halts WHERE scope=?', (scope,)).fetchone()[0]
            if latest is not None and start < latest + 86400:
                raise ValueError('Duplicate, backward or overlapping session')
            db.execute('INSERT INTO daily_risk_halts VALUES (?,?,?,?,?)', (scope, start, policy, start, '[]'))

    def observe(self, *, scope, day_start_utc, now_utc, policy, reasons):
        import json
        self._key(scope); self._key(policy)
        start, now = self._time(day_start_utc), self._time(now_utc)
        if not start <= now < start + 86400 or day_start_utc.microsecond != 0:
            raise ValueError('Observation outside session')
        if not isinstance(reasons, (list, tuple, set, frozenset)) or any(r not in self.REASONS for r in reasons):
            raise ValueError('Unknown daily latch reason')
        with closing(self._connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            self._validate(db)
            latest = db.execute('SELECT MAX(session) FROM daily_risk_halts WHERE scope=?', (scope,)).fetchone()[0]
            row = db.execute('SELECT policy,last_at,reasons FROM daily_risk_halts WHERE scope=? AND session=?', (scope, start)).fetchone()
            if row is None or latest != start:
                raise ValueError('Explicit active session initialization required')
            stored_policy, last_at, encoded = row
            if stored_policy != policy or type(last_at) not in (int, float) or not number(last_at) or not start <= last_at <= now:
                raise ValueError('Policy mismatch, corrupt state or reversed observation')
            old = json.loads(encoded)
            if not isinstance(old, list) or any(r not in self.REASONS for r in old) or len(old) != len(set(old)):
                raise ValueError('Corrupt daily latch reasons')
            held = sorted(set(old) | set(reasons))
            db.execute('UPDATE daily_risk_halts SET last_at=?,reasons=? WHERE scope=? AND session=?',
                       (now, json.dumps(held), scope, start))
        return dict(status='LATCHED_STOP' if held else 'RESEARCH_NO_OBSERVED_STOP',
                    reasons=held, execution_allowed=False)
