"""Pinned catalog of contiguous single-symbol tick archives; research only.

Reuses archive hashing/re-auditing. No broker capture, implicit resume,
calendar inference, deduplication, full-market coverage or trading permission.
"""
from hashlib import sha256
from pathlib import Path
from lsr04_tick_archive import (
    _options, _encode, _decode, _pin, _read_metadata, _write_exclusive,
    save_tick_archive, verify_tick_archive)
from lsr04_tick_quality import _time


BOUND_KEYS = {'start_utc','end_utc','windows','sessions'}


def _shared(options):
    # Session intervals and capture windows vary per chunk; their provenance,
    # symbol/specification and all other audit settings must match exactly.
    return {key:value for key,value in options.items() if key not in BOUND_KEYS}


def _budgets(max_chunks, max_total_ticks):
    if type(max_chunks) is not int or not 1 <= max_chunks <= 10000:
        raise ValueError('Invalid chunk budget')
    if type(max_total_ticks) is not int or not 1 <= max_total_ticks <= 100000000:
        raise ValueError('Invalid total tick budget')


def save_tick_catalog(path, chunks, *, start_utc, end_utc,
                      max_chunks=1000, max_total_ticks=100000000):
    """chunks yields {ticks: iterable, audit_options: explicit options}."""
    _budgets(max_chunks,max_total_ticks)
    start,end = _time(start_utc),_time(end_utc)
    if start >= end:raise ValueError('Increasing catalog bounds required')
    root = Path(path);root.mkdir()
    entries=[];cursor=start;total=0;shared=None
    for index,chunk in enumerate(chunks):
        if index >= max_chunks:raise ValueError('Chunk budget exceeded')
        if not isinstance(chunk,dict) or set(chunk) != {'ticks','audit_options'}:
            raise ValueError('Explicit chunk ticks/options required')
        options = _options(chunk['audit_options'])
        a,b = _time(options['start_utc']),_time(options['end_utc'])
        if a != cursor or not a < b <= end:
            raise ValueError('Chunk gap, overlap, reversal or bounds mismatch')
        current = _shared(options)
        if shared is None:shared=current
        elif _encode(current) != _encode(shared):
            raise ValueError('Mixed source, symbol, broker specification or audit policy')
        name=f'chunk-{index:06d}'
        def rows(source=chunk['ticks']):
            nonlocal total
            for row in source:
                total+=1
                if total > max_total_ticks:raise ValueError('Total tick budget exceeded')
                yield row
        saved=save_tick_archive(root/name,rows(),audit_options=options)
        entries.append(dict(directory=name,start_msc=a,end_msc=b,
            manifest_sha256=saved['manifest_sha256'],
            audit_config_sha256=saved['audit_config_sha256'],
            row_count=saved['row_count'],quality_status=saved['quality_status']))
        cursor=b
    if not entries or cursor != end:raise ValueError('Empty or incomplete catalog horizon')
    catalog=dict(schema_version=1,start_msc=start,end_msc=end,
                 shared_audit_options=shared,total_rows=total,chunks=entries)
    data=_encode(catalog)
    if len(data)>64*1024*1024:raise ValueError('Catalog metadata budget exceeded')
    _write_exclusive(root/'catalog.json',data)  # final completion marker
    return dict(status='SAVED_LOCAL_TICK_CATALOG',catalog_sha256=sha256(data).hexdigest(),
                chunk_count=len(entries),total_rows=total,
                shared_options_sha256=sha256(_encode(shared)).hexdigest(),
                completeness_verified=False,backtest_ready=False,execution_allowed=False)


def verify_tick_catalog(path, *, expected_catalog_sha256,
                        expected_shared_options_sha256=None,
                        max_chunks=1000,max_total_ticks=100000000):
    _budgets(max_chunks,max_total_ticks);_pin(expected_catalog_sha256)
    if expected_shared_options_sha256 is not None:_pin(expected_shared_options_sha256)
    root=Path(path)
    if root.is_symlink() or not root.is_dir():raise ValueError('Regular catalog directory required')
    data=_read_metadata(root/'catalog.json')
    if sha256(data).hexdigest()!=expected_catalog_sha256:raise ValueError('Independent catalog pin mismatch')
    catalog=_decode(data)
    keys={'schema_version','start_msc','end_msc','shared_audit_options','total_rows','chunks'}
    if not isinstance(catalog,dict) or set(catalog)!=keys or type(catalog['schema_version']) is not int or catalog['schema_version']!=1:
        raise ValueError('Unsupported catalog schema')
    for key in ('start_msc','end_msc','total_rows'):
        if type(catalog[key]) is not int:raise ValueError('Invalid catalog count/time')
    start,end=catalog['start_msc'],catalog['end_msc']
    if start>=end or not 0 <= catalog['total_rows'] <= max_total_ticks:
        raise ValueError('Invalid horizon or total row budget')
    entries=catalog['chunks']
    if not isinstance(entries,list) or not 1<=len(entries)<=max_chunks:
        raise ValueError('Invalid catalog chunk count')
    expected_names={'catalog.json'} | {f'chunk-{i:06d}' for i in range(len(entries))}
    if {p.name for p in root.iterdir()} != expected_names:
        raise ValueError('Missing or unexpected catalog members')
    shared=catalog['shared_audit_options'];shared_pin=sha256(_encode(shared)).hexdigest()
    if expected_shared_options_sha256 is not None and shared_pin!=expected_shared_options_sha256:
        raise ValueError('Expected shared audit policy mismatch')
    cursor=start;total=0;blocked=0;review_reasons=set()
    entry_keys={'directory','start_msc','end_msc','manifest_sha256','audit_config_sha256','row_count','quality_status'}
    for index,entry in enumerate(entries):
        if not isinstance(entry,dict) or set(entry)!=entry_keys or entry['directory']!=f'chunk-{index:06d}':
            raise ValueError('Invalid or unsafe chunk reference')
        if any(type(entry[k]) is not int for k in ('start_msc','end_msc','row_count')):
            raise ValueError('Invalid chunk count/time')
        if entry['start_msc']!=cursor or not cursor<entry['end_msc']<=end or entry['row_count']<0:
            raise ValueError('Catalog gap, overlap or reversed interval')
        if total+entry['row_count']>max_total_ticks:raise ValueError('Catalog exceeds total row budget')
        verified=verify_tick_archive(root/entry['directory'],
            expected_manifest_sha256=entry['manifest_sha256'],
            expected_audit_config_sha256=entry['audit_config_sha256'],
            max_ticks=max(1,max_total_ticks-total))
        options=verified['audit_options'];audit=verified['audit']
        if _time(options['start_utc'])!=cursor or _time(options['end_utc'])!=entry['end_msc']:
            raise ValueError('Catalog/archive horizon mismatch')
        if _encode(_shared(options))!=_encode(shared):raise ValueError('Mixed chunk policy or provenance')
        if verified['row_count']!=entry['row_count'] or audit['status']!=entry['quality_status']:
            raise ValueError('Catalog/archive count or quality mismatch')
        total+=verified['row_count'];cursor=entry['end_msc']
        blocked+=audit['status']=='BLOCKED_TICK_QUALITY'
        review_reasons.update(audit['review_reasons'])
    if cursor!=end or total!=catalog['total_rows']:raise ValueError('Incomplete catalog or total count mismatch')
    return dict(status='VERIFIED_LOCAL_CATALOG_ONLY',chunk_count=len(entries),total_rows=total,
                catalog_sha256=expected_catalog_sha256,shared_options_sha256=shared_pin,
                requested_start_msc=start,requested_end_msc=end,blocked_quality_chunks=blocked,
                review_reasons=sorted(review_reasons),completeness_verified=False,
                backtest_ready=False,execution_allowed=False,
                caveat='Verifies contiguous declared archive bounds and local bytes, not complete broker history. Quality audits are per chunk; cross-chunk quote-silence analysis and strategy consumption remain separate.')
