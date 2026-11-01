# SPDX-License-Identifier: GPL-3.0-only
"""Pinned append-only HalfTrend observation batches with replay-on-restore.

Reuses the existing exclusive writer, JSON reader, worker lock, SignalJournal
and HalfTrendObserver. Dedicated local folder only; no MT5/network/orders.
"""
from hashlib import sha256
import inspect
from pathlib import Path
from lsr04_tick_archive import _encode, _decode, _read_metadata, _write_exclusive, _pin
from lsr04_signal_journal import SignalJournal
from lsr05_observation import HalfTrendObserver
from orrery_research_worker import worker_lock

MAX_BYTES=64*1024*1024


def _hash(data): return sha256(data).hexdigest()


def _code_pins():
    paths=[Path(__file__),Path(inspect.getsourcefile(HalfTrendObserver)),
           Path(inspect.getsourcefile(SignalJournal))]
    return {p.name:_hash(p.read_text(encoding='utf-8').encode('utf-8')) for p in paths}


def create_store(path, *, max_batches=1000, max_events=100000):
    if (type(max_batches) is not int or not 1<=max_batches<=1000
            or type(max_events) is not int or not 1<=max_events<=500000):
        raise ValueError('Bounded observation store limits required')
    config=dict(schema_version=1,max_batches=max_batches,max_events=max_events,
                max_bytes=MAX_BYTES,code_sha256=_code_pins(),execution_allowed=False)
    data=_encode(config); root=Path(path); root.mkdir()
    _write_exclusive(root/'store.json',data)
    return dict(status='EMPTY_OBSERVATION_STORE_CREATED',head_sha256=_hash(data),
                batches=0,execution_allowed=False)


def _root(path):
    root=Path(path)
    if root.is_symlink() or not root.is_dir(): raise ValueError('Regular dedicated store folder required')
    metadata=root/'store.json'
    if metadata.is_symlink() or not metadata.is_file():
        raise ValueError('Existing observation store metadata required before locking')
    lock=root/'worker.lock'
    if lock.is_symlink() or (lock.exists() and not lock.is_file()):
        raise ValueError('Regular owner lock required')
    return root


def _restore_locked(root, expected_head_sha256):
    _pin(expected_head_sha256)
    config_bytes=_read_metadata(root/'store.json'); config=_decode(config_bytes)
    if (not isinstance(config,dict) or set(config)!={'schema_version','max_batches','max_events',
            'max_bytes','code_sha256','execution_allowed'} or type(config['schema_version']) is not int
            or config['schema_version']!=1 or config['execution_allowed'] is not False
            or config['code_sha256']!=_code_pins() or config['max_bytes']!=MAX_BYTES
            or type(config['max_batches']) is not int or not 1<=config['max_batches']<=1000
            or type(config['max_events']) is not int or not 1<=config['max_events']<=500000):
        raise ValueError('Unsupported configuration or observation implementation changed')
    members={p.name for p in root.iterdir()}
    count=len(members-{'store.json','worker.lock'})
    if (count>config['max_batches'] or members!={'store.json','worker.lock',
            *(f'batch-{i:06d}' for i in range(count))}):
        raise ValueError('Missing, unexpected or nonconsecutive observation batch')
    monitor=HalfTrendObserver(SignalJournal(),max_events=config['max_events'])
    previous=_hash(config_bytes); total=len(config_bytes); rows_seen=0
    if total>config['max_bytes']: raise ValueError('Store metadata exceeds read budget')
    for index in range(count):
        folder=root/f'batch-{index:06d}'
        if folder.is_symlink() or not folder.is_dir() or {p.name for p in folder.iterdir()}!={'request.json','result.json','complete.json'}:
            raise ValueError('Incomplete observation batch; no silent resume')
        request_bytes=_read_metadata(folder/'request.json')
        result_bytes=_read_metadata(folder/'result.json')
        marker_bytes=_read_metadata(folder/'complete.json')
        total+=len(request_bytes)+len(result_bytes)+len(marker_bytes)
        if total>config['max_bytes']: raise ValueError('Observation read budget exceeded')
        marker=_decode(marker_bytes)
        expected=dict(schema_version=1,index=index,previous_sha256=previous,
                      request_sha256=_hash(request_bytes),result_sha256=_hash(result_bytes),
                      execution_allowed=False)
        if marker!=expected or _encode(expected)!=marker_bytes:
            raise ValueError('Observation chain or payload hash mismatch')
        request=_decode(request_bytes)
        if (not isinstance(request,dict) or set(request)!={'snapshot','arguments'}
                or not isinstance(request['snapshot'],dict) or not isinstance(request['arguments'],dict)
                or not isinstance(request['snapshot'].get('rows'),list)):
            raise ValueError('Unsupported observation request')
        rows_seen+=len(request['snapshot'].get('rows',[]))
        if rows_seen>500000: raise ValueError('Observation replay budget exceeded')
        fresh=monitor.observe(request['snapshot'],**request['arguments'])
        if _encode(fresh)!=result_bytes: raise ValueError('Replayed observation differs from saved result')
        previous=_hash(marker_bytes)
    if previous!=expected_head_sha256: raise ValueError('Retained head pin mismatch; stale or replaced store')
    return monitor,config,previous,count,total,rows_seen


def restore_store(path, *, expected_head_sha256):
    root=_root(path)
    with worker_lock(root):
        monitor,_,head,count,_,_=_restore_locked(root,expected_head_sha256)
        return dict(status='REPLAYED_LOCAL_OBSERVATIONS_ONLY',head_sha256=head,batches=count,
                    report=monitor.report(),broker_authenticity_verified=False,
                    nonrepainting_verified=False,market_edge_verified=False,execution_allowed=False)


def append_snapshot(path, *, expected_head_sha256, snapshot, symbol, observed_at,
                    data_source, implementation_version):
    root=_root(path)
    request=_decode(_encode(dict(snapshot=snapshot,arguments=dict(symbol=symbol,
        observed_at=observed_at,data_source=data_source,implementation_version=implementation_version))))
    if not isinstance(request['snapshot'],dict) or not isinstance(request['snapshot'].get('rows'),list):
        raise ValueError('Explicit snapshot rows required')
    with worker_lock(root):
        monitor,config,head,count,total,rows_seen=_restore_locked(root,expected_head_sha256)
        if count>=config['max_batches']: raise ValueError('Observation batch capacity reached')
        if rows_seen+len(request['snapshot'].get('rows',[]))>500000:
            raise ValueError('Observation replay budget exceeded')
        result=monitor.observe(request['snapshot'],**request['arguments'])
        request_bytes=_encode(request); result_bytes=_encode(result)
        marker_bytes=_encode(dict(schema_version=1,index=count,previous_sha256=head,
            request_sha256=_hash(request_bytes),result_sha256=_hash(result_bytes),execution_allowed=False))
        if total+len(request_bytes)+len(result_bytes)+len(marker_bytes)>config['max_bytes']:
            raise ValueError('Observation write budget exceeded')
        folder=root/f'batch-{count:06d}'; folder.mkdir()
        _write_exclusive(folder/'request.json',request_bytes)
        _write_exclusive(folder/'result.json',result_bytes)
        _write_exclusive(folder/'complete.json',marker_bytes)  # final completion marker
        return dict(status='OBSERVATION_BATCH_SAVED',head_sha256=_hash(marker_bytes),
                    batches=count+1,observation=result,execution_allowed=False)
