"""Pinned tick catalog -> LSR02/03 matched candidate price-R study.

Independent outcomes may overlap. Caller OHLC provenance is not verified by
quote hashes. Costs are explicit quote-price-per-unit assumptions, not broker
currency costs. No account curve, strategy approval, 2.6 replacement or orders.
"""
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from math import isfinite
from pathlib import Path
import json
from lsr03_adapter import compare_vhf, collect_retests
from lsr04_tick_fills import replay_exit
from lsr04_tick_quality import audit_ticks
from lsr04_tick_archive import _decode, _read_metadata, MAX_LINE_BYTES
from lsr04_tick_catalog import verify_tick_catalog


def _positive(value, zero=False):
    if type(value) not in (int,float) or not isfinite(value) or (value < 0 if zero else value <= 0):
        raise ValueError('Finite explicit research parameter required')
    return value


def _summary(rows):
    closed=[r for r in rows if r['status']=='CLOSED']
    values=[r['net_r'] for r in closed]
    wins=[r for r in values if r>0];losses=[r for r in values if r<0]
    return dict(candidates=len(rows),closed=len(closed),
        unresolved=sum(r['status']=='OPEN' for r in rows),
        not_filled=sum(r['status'] not in ('OPEN','CLOSED') for r in rows),
        total_net_r=sum(values),expectancy_r=sum(values)/len(values) if values else None,
        win_rate=len(wins)/len(values) if values else None,
        average_win_r=sum(wins)/len(wins) if wins else None,
        average_loss_r=sum(losses)/len(losses) if losses else None,
        profit_factor_r=sum(wins)/(-sum(losses)) if losses else None)


def load_catalog_ticks(path, *, expected_catalog_sha256, bar_source, as_of, max_ticks=500000):
    """Shared bounded pinned loader/global audit; not a strategy approval."""
    if type(max_ticks) is not int or not 1<=max_ticks<=2000000:
        raise ValueError('Pilot tick budget required')
    _positive(as_of)
    root=Path(path)
    integrity=verify_tick_catalog(root,expected_catalog_sha256=expected_catalog_sha256,
                                 max_total_ticks=max_ticks)
    catalog_bytes=_read_metadata(root/'catalog.json')
    if sha256(catalog_bytes).hexdigest()!=expected_catalog_sha256:raise ValueError('Catalog changed')
    catalog=_decode(catalog_bytes);shared=catalog['shared_audit_options']
    if not isinstance(bar_source,str) or bar_source!=shared['source']:
        raise ValueError('Bar/tick source labels must match explicitly')
    if as_of*1000!=catalog['end_msc']:raise ValueError('Study end must match pinned tick horizon')
    ticks=[];windows=[];sessions=[];has_windows=True;has_sessions=True
    for chunk in catalog['chunks']:
        folder=root/chunk['directory'];data=_read_metadata(folder/'manifest.json')
        if sha256(data).hexdigest()!=chunk['manifest_sha256']:raise ValueError('Chunk manifest changed')
        manifest=_decode(data);options=manifest['audit_options']
        if options['windows'] is None:has_windows=False
        else:windows.extend(options['windows'])
        if options['sessions'] is None:has_sessions=False
        else:sessions.extend(options['sessions'])
        digest=sha256();size=0;count=0
        with (folder/'ticks.jsonl').open('rb') as stream:
            while True:
                line=stream.readline(MAX_LINE_BYTES+1)
                if not line:break
                if len(line)>MAX_LINE_BYTES or not line.endswith(b'\n'):raise ValueError('Invalid tick line')
                digest.update(line);size+=len(line);count+=1
                ticks.append(_decode(line))
                if len(ticks)>max_ticks:raise ValueError('Pilot row budget exceeded')
        if digest.hexdigest()!=manifest['ticks_sha256'] or size!=manifest['ticks_bytes'] or count!=manifest['row_count']:
            raise ValueError('Tick archive changed during study read')
    epoch=datetime(1970,1,1,tzinfo=timezone.utc)
    options=dict(shared,start_utc=epoch+timedelta(milliseconds=catalog['start_msc']),
                 end_utc=epoch+timedelta(milliseconds=catalog['end_msc']),
                 windows=windows if has_windows else None,
                 sessions=sessions if has_sessions else None,max_ticks=max_ticks)
    global_audit=audit_ticks(ticks,**options)
    return dict(integrity=integrity,ticks=ticks,audit=global_audit,symbol=shared['symbol'],
        blocked=bool(global_audit['issues'] or global_audit['counts']['open_session_gap_candidates']
                     or global_audit['counts']['unknown_session_gaps'] or not has_windows),
        start_msc=catalog['start_msc'],end_msc=catalog['end_msc'])


def study_catalog(path, *, expected_catalog_sha256, h4, m15, m5, bar_source,
                  as_of, buffer, target_r, round_trip_cost_per_unit, slippage,
                  entry_delay_msc=1, period=14, min_vhf=.4, left=1, right=1,
                  lifetime=6000, max_ticks=500000, max_candidates=1000,
                  max_candidate_tick_visits=5000000):
    """First RETEST per existing candidate, target is explicit research fixed R.

    Source label agreement is a consistency check, not OHLC authentication.
    Fixed R is an execution benchmark, never the author's 2.6 method.
    """
    for value in (buffer,target_r,lifetime):_positive(value)
    for value in (round_trip_cost_per_unit,slippage):_positive(value,True)
    if type(entry_delay_msc) is not int or entry_delay_msc<1:
        raise ValueError('Strictly post-confirmation entry delay required')
    if type(max_ticks) is not int or not 1<=max_ticks<=2000000 or type(max_candidates) is not int or not 1<=max_candidates<=10000:
        raise ValueError('Explicit pilot study budgets required')
    if type(max_candidate_tick_visits) is not int or not 1<=max_candidate_tick_visits<=100000000:
        raise ValueError('Explicit replay work budget required')
    _positive(as_of)
    loaded=load_catalog_ticks(path,expected_catalog_sha256=expected_catalog_sha256,
        bar_source=bar_source,as_of=as_of,max_ticks=max_ticks)
    ticks=loaded['ticks'];global_audit=loaded['audit'];symbol=loaded['symbol']
    if loaded['blocked']:
        return dict(status='BLOCKED_GLOBAL_TICK_QUALITY',audit=global_audit,
                    integrity=loaded['integrity'],rows=[],execution_allowed=False,
                    market_edge_verified=False)
    catalog=dict(start_msc=loaded['start_msc'],end_msc=loaded['end_msc'])
    compared=compare_vhf(symbol,h4,m15,m5,as_of=as_of,buffer=buffer,period=period,
                         min_vhf=min_vhf,left=left,right=right,lifetime=lifetime)
    candidates=collect_retests(compared,symbol,max_candidates=max_candidates)
    rows=[];tick_visits=0
    from bisect import bisect_left
    clock=[q['time_msc'] for q in ticks]
    for c in candidates:
        row=dict(id=c['id'],side=c['side'],group=c['group'],structural_at=c['retest_at'],
                 stop=c['stop'],status='NO_ENTRY_QUOTE')
        requested=c['retest_at']*1000+entry_delay_msc
        if requested<catalog['start_msc']:
            row['status']='OUTSIDE_TICK_COVERAGE';rows.append(row);continue
        index=bisect_left(clock,requested)
        if index>=len(ticks):rows.append(row);continue
        first=ticks[index];at=first['time_msc']
        expiry=(c['sweep_at']+lifetime)*1000
        invalid=c['invalid_at']*1000 if c['invalid_at'] is not None else expiry
        if at>=min(expiry,invalid):
            row['status']='CANDIDATE_EXPIRED_BEFORE_FILL';rows.append(row);continue
        entry=first['ask']+slippage if c['side']=='BUY' else first['bid']-slippage
        distance=entry-c['stop'] if c['side']=='BUY' else c['stop']-entry
        if entry<=0 or distance<=0:
            row['status']='INVALID_STRUCTURE';rows.append(row);continue
        target=entry+distance*target_r if c['side']=='BUY' else entry-distance*target_r
        if target<=0 or not isfinite(target):
            row['status']='INVALID_STRUCTURE';rows.append(row);continue
        tick_visits+=len(ticks)-index
        if tick_visits>max_candidate_tick_visits:raise ValueError('Candidate tick-replay budget exceeded')
        # Reuse the existing Bid/Ask/gap fill implementation; no parallel fill model.
        outcome=replay_exit(ticks[index:],side=c['side'],entry_after_msc=requested,
                            stop_price=c['stop'],target_price=target,slippage=slippage)
        row.update(outcome,target=target,initial_price_risk=distance)
        if outcome['status']=='CLOSED':
            _positive(outcome['exit_price'])
            row.update(gross_r=outcome['price_pnl_per_unit']/distance,
                       cost_r=round_trip_cost_per_unit/distance,
                       net_r=(outcome['price_pnl_per_unit']-round_trip_cost_per_unit)/distance)
            if not all(isfinite(row[k]) for k in ('gross_r','cost_r','net_r')):raise ValueError('Outcome overflow')
        rows.append(row)
    selected=[r for r in rows if r['group']=='VHF_PASS']
    filtered=[r for r in rows if r['group']=='VHF_FILTERED']
    closed_filtered=[r for r in filtered if r['status']=='CLOSED']
    return dict(status='MATCHED_TICK_CANDIDATE_RESEARCH',symbol=symbol,rows=rows,
        summaries=dict(LSR02=_summary(rows),LSR03=_summary(selected),VHF_FILTERED=_summary(filtered)),
        avoided_loss_r=-sum(r['net_r'] for r in closed_filtered if r['net_r']<0),
        missed_profit_r=sum(r['net_r'] for r in closed_filtered if r['net_r']>0),
        global_tick_audit=global_audit,catalog_sha256=expected_catalog_sha256,
        bar_source=bar_source,bar_provenance_verified=False,
        bar_input_sha256=sha256(json.dumps([h4,m15,m5],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),
        entry_rule='FIRST_RETEST_THEN_POST_CONFIRMATION_QUOTE',
        target_rule='EXPLICIT_FIXED_R_BENCHMARK_NOT_2_6',target_r=target_r,
        round_trip_cost_per_unit=round_trip_cost_per_unit,slippage=slippage,
        entry_delay_msc=entry_delay_msc,
        strategy_config=dict(buffer=buffer,period=period,min_vhf=min_vhf,left=left,right=right,lifetime=lifetime),
        cost_basis='EXPLICIT_QUOTE_PRICE_PER_UNIT_NOT_BROKER_CURRENCY',
        portfolio_metrics_available=False,
        market_edge_verified=False,execution_allowed=False,
        caveat='Independent candidate outcomes may overlap. OHLC source label is not proof; costs are quote-price-unit assumptions. No broker-currency profit, Type-A formal certification, daily/portfolio simulation, margin, real-market edge or OOS claim.')
