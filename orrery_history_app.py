"""Offline public-history research using existing LSR02/VHF03 engines; no MT5."""
import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from orrery_tradingview_window_replay import _aligned_windows, _one_window, _summary
from orrery_public_xau_m1_audit import inspect
from orrery_dashboard_analysis import analyze
from orrery_public_m1_gap_inventory import inventory as m1_gap_inventory

PARAMETERS = dict(buffer=.1, target_r=2, period=14, min_vhf=.4, left=1, right=1, lifetime=6000)
STEPS = {'5m':300, '15m':900, '4H':14400}


def frames(folder):
    result = {}
    for label, step in STEPS.items():
        code = {'5m':'M5', '15m':'M15', '4H':'H4'}[label]
        path = folder / f'XAUUSD_{code}_UNVERIFIED_QUOTE.csv'
        rows = []
        with path.open(encoding='utf-8', newline='') as stream:
            for row in csv.DictReader(stream):
                t = datetime.fromisoformat(row['timestamp_utc'])
                if t.utcoffset() is None or t.utcoffset().total_seconds() != 0:
                    raise ValueError('Explicit UTC required')
                rows.append(dict(close_time=int(t.timestamp())+step,
                    **{k:float(row['bid_'+k]) for k in ('open','high','low','close')}))
        # Validate OHLC, clocks and individual gaps without filling missing bars.
        from math import isfinite
        for i, b in enumerate(rows):
            if (not all(isfinite(b[k]) for k in ('open','high','low','close'))
                    or not 0 < b['low'] <= min(b['open'],b['close']) <= max(b['open'],b['close']) <= b['high']
                    or b['close_time'] % step or i and b['close_time'] <= rows[i-1]['close_time']):
                raise ValueError('Invalid history bars')
        if not rows or len(rows)>200000:
            raise ValueError('Bounded nonempty history required')
        result[label] = rows
    return result


def compare(data):
    rows = []; windows = []
    for window in _aligned_windows({'5m':data['5m'], '15m':data['15m'], '4h':data['4H']}):
        candidates, _ = _one_window(window, PARAMETERS)
        rows.extend(candidates)
        windows.append(dict(start=window['start_s'], end=window['end_s'], candidates=len(candidates)))
    return dict(parameters=PARAMETERS, parameters_optimized=False, windows=windows,
        summaries=dict(LSR02=_summary(rows), VHF03=_summary([r for r in rows if r['vhf_group']=='VHF_PASS'])),
        source_price_basis='PUBLIC_UNVERIFIED_OHLC', reset_at_gaps=True,
        bid_ask_costs_verified=False, independent_holdout=False, actual_profit_usd=None,
        execution_allowed=False, candidates=rows)


def coverage(data):
    result={}
    for label, rows in data.items():
        step=STEPS[label]; longest=current=1; gaps=0
        for previous, row in zip(rows,rows[1:]):
            if row['close_time']-previous['close_time']==step:
                current+=1
            else:
                gaps+=1;current=1
            longest=max(longest,current)
        result[label]=dict(rows=len(rows), gap_count=gaps, longest_contiguous_bars=longest,
            first_open_utc=datetime.fromtimestamp(rows[0]['close_time']-step,timezone.utc).isoformat(),
            last_close_utc=datetime.fromtimestamp(rows[-1]['close_time'],timezone.utc).isoformat(),
            session_calendar_verified=False)
    return result


def crosscheck(source, data):
    """Check each retained parent against every source minute, without filling gaps."""
    minutes={}
    with source.open(encoding='utf-8-sig',newline='') as stream:
        for row in csv.DictReader(stream):
            at=datetime.fromisoformat(row['datetime'].replace('Z','+00:00'))
            if at.utcoffset() is None or at.utcoffset().total_seconds()!=0:
                raise ValueError('Source requires UTC')
            minutes[int(at.timestamp())]={k:float(row[k]) for k in ('open','high','low','close')}
    report={}
    for label, rows in data.items():
        step=STEPS[label]
        for row in rows:
            children=[minutes.get(t) for t in range(row['close_time']-step,row['close_time'],60)]
            if any(c is None for c in children):
                raise ValueError('Aggregated parent crosses missing M1')
            expected=dict(open=children[0]['open'],close=children[-1]['close'],
                          high=max(c['high'] for c in children),low=min(c['low'] for c in children))
            if any(abs(expected[k]-row[k])>1e-8 for k in expected):
                raise ValueError('Parent OHLC does not match source M1')
        report[label]=dict(checked_parents=len(rows),mismatches=0)
    return report


def snapshot(folder, comparison=None):
    data = frames(folder)
    charts = []
    for label, rows in data.items():
        step = STEPS[label]
        start = len(rows)-1
        while start>0 and len(rows)-start<100 and rows[start]['close_time']-rows[start-1]['close_time']==step:
            start-=1
        charts.append(dict(symbol='XAUUSD', timeframe=label, status='CLOSED_BARS_AVAILABLE',
            last_close_utc=datetime.fromtimestamp(rows[-1]['close_time'],timezone.utc).isoformat(),
            bars=[dict(time=b['close_time']-step, **{k:b[k] for k in ('open','high','low','close')}) for b in rows[start:]]))
    source = dict(status='PUBLIC_HISTORY_RESEARCH', charts=charts, quotes=[], positions=[],
        broker_server='PUBLIC OHLC / OFFLINE / NOT MT5', account_last4='----', currency='USD',
        balance=None, equity=None, margin_free=None, history_7d_count=None,
        checked_at_utc='HISTORICAL DATA — NOT CURRENT', execution_allowed=False)
    source['analysis'] = analyze(source, 0)
    source['research_results'] = comparison
    return source


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bars',type=Path,required=True)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        parser.error('New output only')
    audit=inspect(args.source)
    data=frames(args.bars)
    result=compare(data)
    result['audit']=audit
    result['m1_gap_inventory']=m1_gap_inventory(args.source)
    result['aggregation_crosscheck']=crosscheck(args.source,data)
    result['frame_counts']={k:len(v) for k,v in data.items()}
    result['frame_coverage']=coverage(data)
    hours={str(hour):0 for hour in range(24)};months={}
    with args.source.open(encoding='utf-8-sig',newline='') as stream:
        for row in csv.DictReader(stream):
            at=datetime.fromisoformat(row['datetime'].replace('Z','+00:00'))
            if at.utcoffset() is None or at.utcoffset().total_seconds()!=0:
                raise ValueError('Source requires explicit UTC')
            hours[str(at.hour)]+=1
            month=at.strftime('%Y-%m');months[month]=months.get(month,0)+1
    result['source_rows_by_utc_hour']=hours
    result['source_rows_by_month']=months
    result['bars_sha256']={p.name:sha256(p.read_bytes()).hexdigest() for p in args.bars.glob('*.csv')}
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2,allow_nan=False)
    print(json.dumps(dict(counts=result['frame_counts'],summaries=result['summaries']),allow_nan=False))
