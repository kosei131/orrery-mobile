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
