"""One-entry local preparation, DEMO intake and offline verification.

Default mode prepares only. No installation, login, orders or automatic restart.
"""
import argparse,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone
from orrery_h4_reconciliation_plan import save_plan
from orrery_h4_reconciliation_batch import run_batch,load_plan
from orrery_h4_batch_verify import verify_batch
from orrery_h4_batch_chain import audit_chain
from lsr04_tick_archive import _encode,_write_exclusive


def workflow(*, output, execute=False, max_chunks=1, mt5=None, now=None):
    if type(execute) is not bool or type(max_chunks) is not int or not 1<=max_chunks<=456:
        raise ValueError('Explicit bounded execution settings required')
    if execute and mt5 is None:raise ValueError('Initialized DEMO adapter required')
    root=Path(output);root.mkdir(exist_ok=False)
    plan=save_plan(root/'plan');pin=plan['request_sha256']
    load_plan(root/'plan/request.json',pin)
    result=dict(status='PREPARED_NOT_EXECUTED',plan_sha256=pin,requested_chunks=max_chunks,
        acquisition_attempted=False,backtest_ready=False,execution_allowed=False,
        source_sha256={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
            for n in ('orrery_h4_pc_workflow.py','orrery_h4_reconciliation_plan.py',
                      'orrery_h4_reconciliation_batch.py','orrery_h4_batch_verify.py',
                      'orrery_h4_batch_chain.py')})
    if execute:
        result['acquisition_attempted']=True
        try:
            batch=run_batch(mt5,plan_path=root/'plan/request.json',plan_sha256=pin,
                output=root/'batch',max_chunks=max_chunks,now=now)
            verify_batch(root/'batch',expected_result_sha256=batch['result_sha256'])
            manifest=[dict(path=str((root/'batch').resolve()),result_sha256=batch['result_sha256'])]
            manifest_raw=_encode(manifest)
            _write_exclusive(root/'runs.json',manifest_raw)
            chain=audit_chain(manifest)
            chain_raw=_encode(chain);_write_exclusive(root/'chain_review.json',chain_raw)
            result.update(status='BLOCKED_WORKFLOW' if batch['status']=='BLOCKED_BATCH' else
                          'REQUESTED_CHUNKS_VERIFIED_REVIEW_REQUIRED',
                batch_result_sha256=batch['result_sha256'],saved_chunks=batch['saved_chunks'],
                runs_sha256=hashlib.sha256(manifest_raw).hexdigest(),
                chain_review_sha256=hashlib.sha256(chain_raw).hexdigest(),
                remaining_chunks=chain['remaining_chunks'])
        except Exception:
            result['status']='BLOCKED_WORKFLOW'
    raw=_encode(result);_write_exclusive(root/'workflow_result.json',raw)
    return dict(result,workflow_result_sha256=hashlib.sha256(raw).hexdigest())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True);p.add_argument('--execute',action='store_true')
    p.add_argument('--max-chunks',type=int,default=1)
    p.add_argument('--terminal-path',default=r'C:\Program Files\MetaTrader 5\terminal64.exe')
    a=p.parse_args();mt5=None
    try:
        if a.execute:
            if sys.platform!='win32' or sys.version_info[:2]!=(3,12):
                raise ValueError('Windows Python3.12 required')
            import MetaTrader5 as mt5
            if not mt5.initialize(a.terminal_path,timeout=30000):raise ValueError('Terminal unavailable')
        r=workflow(output=a.output,execute=a.execute,max_chunks=a.max_chunks,mt5=mt5,
                   now=datetime.now(timezone.utc).replace(microsecond=0))
        print(_encode(r).decode());return 2 if r['status']=='BLOCKED_WORKFLOW' else 0
    except Exception:
        print('BLOCKED: preparation or DEMO intake unavailable. Existing output is preserved.');return 1
    finally:
        if mt5 is not None:mt5.shutdown()

if __name__=='__main__':raise SystemExit(main())
