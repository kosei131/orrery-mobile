"""Offline integrity verification; no MT5 import, orders, or restart authority."""
import hashlib
from pathlib import Path
from lsr04_tick_archive import _read_metadata,_decode,verify_tick_archive


def file_pins(root):
    root=Path(root)
    if root.is_symlink() or not root.is_dir():raise ValueError('Regular batch folder required')
    pins={}
    for p in root.rglob('*'):
        if p.is_symlink():raise ValueError('No linked batch paths')
        if not p.is_file() or p==root/'batch_result.json':continue
        if len(pins)>=10000:raise ValueError('File budget exceeded')
        with p.open('rb') as stream:pins[p.relative_to(root).as_posix()]=hashlib.file_digest(stream,'sha256').hexdigest()
    return pins


def verify_batch(path, *, expected_result_sha256):
    from orrery_h4_reconciliation_batch import load_plan
    from orrery_h4_reconciliation_plan import build_plan
    root=Path(path);raw=_read_metadata(root/'batch_result.json')
    if hashlib.sha256(raw).hexdigest()!=expected_result_sha256:raise ValueError('Retained receipt pin mismatch')
    result=_decode(raw)
    if result.get('file_sha256')!=file_pins(root):raise ValueError('Missing, changed or extra batch files')
    load_plan(root/'request.json',result['plan_sha256'])
    count=result['saved_chunks'];requested=result['requested_chunks'];start=result.get('start_chunk',0)
    if type(start) is not int or not 0<=start<456 or type(requested) is not int or start+requested>456:
        raise ValueError('Invalid chunk offset')
    if type(count) is not int or type(requested) is not int or not 0<=count<=requested<=456 or requested<1:
        raise ValueError('Invalid batch counts')
    success=result['status']=='REQUESTED_CHUNKS_SAVED_REVIEW_REQUIRED'
    if (result['status'] not in ('REQUESTED_CHUNKS_SAVED_REVIEW_REQUIRED','BLOCKED_BATCH')
            or (success and (count!=requested or result['failed_chunk_id'] is not None))
            or (not success and (count>=requested or result['failed_chunk_id']!=start+count))
            or any(result.get(k) is not False for k in ('completeness_verified','backtest_ready','execution_allowed'))):
        raise ValueError('Inconsistent batch status')
    expected_progress={'progress-%04d.json'%i for i in range(start,start+count)}
    actual_progress={p.name for p in root.glob('progress-*.json')}
    if expected_progress!=actual_progress:raise ValueError('Progress manifest mismatch')
    for chunk in build_plan()['tick_chunks'][start:start+count]:
        n=chunk['id'];folder=root/('chunk-%04d'%n)
        progress=_decode(_read_metadata(root/('progress-%04d.json'%n)))
        rawcheck=_read_metadata(folder/'history_check.json');check=_decode(rawcheck)
        if (progress.get('chunk_id')!=n or progress.get('status')!='CHUNK_SAVED_REVIEW_REQUIRED'
                or progress.get('history_check_sha256')!=hashlib.sha256(rawcheck).hexdigest()
                or check.get('status')!='HISTORY_SAVED_REVIEW_REQUIRED'):
            raise ValueError('Chunk receipt mismatch')
        request_raw=_read_metadata(folder/'request.json');request=_decode(request_raw)
        if (hashlib.sha256(request_raw).hexdigest()!=check['request_sha256']
                or request['symbol']!='XAUUSD' or request['start_utc']!=chunk['start_utc']
                or request['end_utc']!=chunk['end_utc_exclusive']):
            raise ValueError('Chunk request mismatch')
        archive=verify_tick_archive(folder/'archive',expected_manifest_sha256=check['manifest_sha256'],
            expected_audit_config_sha256=check['audit_config_sha256'])
        if archive['row_count']!=check['rows']:raise ValueError('Archive count mismatch')
    return dict(status='BATCH_BYTES_VERIFIED_ONLY',saved_chunks=count,
        batch_status=result['status'],restart_allowed=False,account_identity_verified=False,
        completeness_verified=False,execution_allowed=False)


if __name__=='__main__':
    import argparse,json
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True)
    parser.add_argument('--result-sha256',required=True)
    args=parser.parse_args()
    print(json.dumps(verify_batch(args.run,expected_result_sha256=args.result_sha256)))
