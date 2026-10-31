"""Bounded DEMO-only chunk intake; never orders or a complete-history claim."""
import argparse,hashlib,sys
from datetime import datetime,timezone
from pathlib import Path
from orrery_h4_reconciliation_plan import build_plan
from orrery_mt5_history_check import check_history
from lsr03_mt5_pilot import _account,_spec
from lsr04_tick_archive import _encode,_decode,_read_metadata,_write_exclusive


def load_plan(path,pin):
    raw=_read_metadata(path)
    if hashlib.sha256(raw).hexdigest()!=pin or _decode(raw)!=build_plan():
        raise ValueError('Pinned exact reconciliation plan required')
    return raw


def run_batch(mt5, *, plan_path, plan_sha256, output, max_chunks, now):
    raw=load_plan(plan_path,plan_sha256)
    if type(max_chunks) is not int or not 1<=max_chunks<=456:
        raise ValueError('Explicit bounded chunk count required')
    identity=_account(mt5);spec=_spec(mt5,'XAUUSD')
    root=Path(output);root.mkdir(exist_ok=False)
    _write_exclusive(root/'request.json',raw)
    _write_exclusive(root/'batch_settings.json',_encode(dict(max_chunks=max_chunks,
        source_sha256={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
                       for n in ('orrery_h4_reconciliation_batch.py','orrery_h4_reconciliation_plan.py',
                                 'orrery_mt5_history_check.py')})))
    completed=0;status='BLOCKED_BATCH';failure=None
    for chunk in build_plan()['tick_chunks'][:max_chunks]:
        try:
            if _account(mt5)!=identity or _spec(mt5,'XAUUSD')!=spec:
                raise ValueError('Identity changed')
            result=check_history(mt5,output=root/('chunk-%04d'%chunk['id']),symbol='XAUUSD',
                start=datetime.fromisoformat(chunk['start_utc']),
                end=datetime.fromisoformat(chunk['end_utc_exclusive']),now=now)
            if _account(mt5)!=identity or _spec(mt5,'XAUUSD')!=spec:
                raise ValueError('Identity changed')
            if result['status']!='HISTORY_SAVED_REVIEW_REQUIRED':
                raise ValueError('Chunk quality blocked')
            _write_exclusive(root/('progress-%04d.json'%chunk['id']),_encode(dict(
                chunk_id=chunk['id'],status='CHUNK_SAVED_REVIEW_REQUIRED',
                history_check_sha256=hashlib.sha256((root/('chunk-%04d'%chunk['id'])/'history_check.json').read_bytes()).hexdigest())))
            completed+=1
        except Exception:
            failure=chunk['id'];break
    else:status='REQUESTED_CHUNKS_SAVED_REVIEW_REQUIRED'
    receipt=dict(status=status,requested_chunks=max_chunks,saved_chunks=completed,
        failed_chunk_id=failure,total_plan_chunks=456,plan_sha256=plan_sha256,
        full_plan_attempted=max_chunks==456,completeness_verified=False,
        backtest_ready=False,execution_allowed=False)
    _write_exclusive(root/'batch_result.json',_encode(receipt))
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',required=True);p.add_argument('--plan-sha256',required=True)
    p.add_argument('--output',required=True);p.add_argument('--max-chunks',type=int,default=1)
    p.add_argument('--execute',action='store_true')
    p.add_argument('--terminal-path',default=r'C:\Program Files\MetaTrader 5\terminal64.exe')
    a=p.parse_args();mt5=None
    try:
        load_plan(a.plan,a.plan_sha256)
        if not a.execute:
            print('PLAN_VERIFIED_NOT_EXECUTED');return 0
        if sys.platform!='win32' or sys.version_info[:2]!=(3,12):
            raise ValueError('Windows Python 3.12 required')
        import MetaTrader5 as mt5
        if not mt5.initialize(a.terminal_path,timeout=30000):raise ValueError('Terminal unavailable')
        r=run_batch(mt5,plan_path=a.plan,plan_sha256=a.plan_sha256,output=a.output,
                    max_chunks=a.max_chunks,now=datetime.now(timezone.utc).replace(microsecond=0))
        print(_encode(r).decode());return 2 if r['status']=='BLOCKED_BATCH' else 0
    except Exception:
        print('BLOCKED: plan, DEMO account, history or persistence unavailable.');return 1
    finally:
        if mt5 is not None:mt5.shutdown()

if __name__=='__main__':raise SystemExit(main())
