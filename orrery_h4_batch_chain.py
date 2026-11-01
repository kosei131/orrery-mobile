"""Explicit ordered receipt chain audit; no terminal, merge or restart."""
import hashlib
from pathlib import Path
from lsr04_tick_archive import _read_metadata,_decode,_encode
from orrery_h4_batch_verify import verify_batch
from orrery_h4_reconciliation_plan import build_plan


def audit_chain(runs):
    if not isinstance(runs,list) or not 1<=len(runs)<=1000:
        raise ValueError('Explicit bounded ordered run list required')
    expected=0;parent=None;plan=None;seen=set();folders=set();attempts=0;retained=[]
    for item in runs:
        if not isinstance(item,dict) or set(item)!={'path','result_sha256'}:
            raise ValueError('Exact run path and retained result pin required')
        root=Path(item['path']);pin=item['result_sha256']
        if pin in seen or root.resolve() in folders:raise ValueError('Repeated run')
        seen.add(pin);folders.add(root.resolve())
        verify_batch(root,expected_result_sha256=pin)
        result=_decode(_read_metadata(root/'batch_result.json'))
        if result.get('start_chunk',0)!=expected or result.get('parent_result_sha256')!=parent:
            raise ValueError('Missing parent, reordered, overlapping or skipped chunk chain')
        if plan is not None and result['plan_sha256']!=plan:raise ValueError('Mixed plan')
        plan=result['plan_sha256'];expected+=result['saved_chunks'];parent=pin
        attempts+=result['status']=='BLOCKED_BATCH'
        retained.append(pin)
    chunks=build_plan()['tick_chunks'];slots=[]
    for slot in build_plan()['slots']:
        ids=[c['id'] for c in chunks if c['slot_id']==slot['id']]
        count=sum(i<expected for i in ids)
        slots.append(dict(slot_id=slot['id'],saved_chunks=count,expected_chunks=24,
            status='ALL_CHUNKS_SAVED_NOT_MARKET_VERIFIED' if count==24 else
                   'PARTIAL' if count else 'NOT_ACQUIRED'))
    return dict(status='BATCH_CHAIN_INTEGRITY_ONLY',runs=len(runs),saved_unique_chunks=expected,
        remaining_chunks=456-expected,next_chunk_id=expected if expected<456 else None,
        blocked_attempts=attempts,all_planned_chunks_saved=expected==456,slots=slots,
        retained_result_pins=retained,plan_sha256=plan,
        chain_pins_sha256=hashlib.sha256(_encode(retained)).hexdigest(),
        account_identity_verified=False,market_completeness_verified=False,
        broker_calendar_verified=False,backtest_ready=False,execution_allowed=False)


if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',required=True);p.add_argument('--manifest-sha256',required=True)
    a=p.parse_args();raw=_read_metadata(a.manifest)
    if hashlib.sha256(raw).hexdigest()!=a.manifest_sha256:raise ValueError('Manifest pin mismatch')
    print(json.dumps(audit_chain(_decode(raw)),indent=2))
