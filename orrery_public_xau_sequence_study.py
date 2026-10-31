"""Exploratory M15 sweep -> M5 structure confirmation; NOT an LSR-02/03 trade.
Uses already closed candles, resets on any missing grid interval, and never
pretends that an unverified H4 trend or broker fills have passed.
"""
import json
from bisect import bisect_right
from pathlib import Path
from lsr02_structure import detect
from lsr03_vhf import calculate
from orrery_real_bars_lsr_bridge import load

def segments(bars, interval):
    result=[];group=[];previous=None
    for b in bars:
        if previous is not None and b["close_time"]-previous!=interval:
            if group:result.append(group)
            group=[]
        group.append(b);previous=b["close_time"]
    if group:result.append(group)
    return result

def observe_retest(candidate, bars, *, deadline_seconds=3600):
    """Observe in close-time order; never discard a touch due to a later gap."""
    at=candidate['confirmation_close']
    poi=candidate['poi']
    if poi is None:
        return dict(status='NO_POI',entry_at=None,observed_until=at)
    if deadline_seconds<=0 or deadline_seconds%300 or poi['low']>poi['high']:
        raise ValueError('Invalid retest specification')
    times=[b['close_time'] for b in bars]
    i=bisect_right(times,at)
    expected=at+300
    last=at
    for b in bars[i:]:
        if b['close_time']>at+deadline_seconds:break
        if b['close_time']!=expected:
            return dict(status='UNKNOWN_HISTORY',entry_at=None,observed_until=last)
        last=b['close_time']
        if b['low']<=poi['high'] and b['high']>=poi['low']:
            return dict(status='RETEST',entry_at=last,observed_until=last)
        expected+=300
    return dict(status='EXPIRED' if last==at+deadline_seconds else 'UNKNOWN_HISTORY',
                entry_at=None,observed_until=last)


def report(root):
    m15=load(root/"XAUUSD_M15_UNVERIFIED_QUOTE.csv","M15")
    m5=load(root/"XAUUSD_M5_UNVERIFIED_QUOTE.csv","M5")
    return report_from_bars(m15['bars'],m5['bars'])


def report_from_bars(m15_bars,m5_bars):
    m15={'bars':m15_bars};m5={'bars':m5_bars}
    events15=[];events5=[]
    for data,interval,out in ((m15,900,events15),(m5,300,events5)):
        for group in segments(data["bars"],interval):
            if len(group)<8:continue
            structured=detect(group,as_of=group[-1]["close_time"],interval=interval)
            for event in structured["events"]:
                if (interval==900 and event["kind"]=="SWEEP") or (
                    interval==300 and event["kind"] in ("BOS","CHoCH")):
                    out.append({"at":event["known_at"],"kind":event["kind"],
                                "direction":event["direction"],
                                "segment_start":group[0]["close_time"],
                                "segment_end":group[-1]["close_time"],"poi":event.get("poi")})
    matched=0;by_side={"BUY":0,"SELL":0}
    vhf_passed=0;vhf_evaluable=0
    vhf_poi=0;vhf_retouch=0
    retouch_evidence=[]
    confirmation_evidence=[]
    retest_observations=[]
    m15_segments=segments(m15["bars"],900)
    used_m5_events=set()
    # Stable chronological one-to-one matching: each M5 event may confirm
    # at most one M15 sweep, and only after its known close.
    for sweep in sorted(events15,key=lambda e:e["at"]):
        target="DOWN" if sweep["direction"]=="UP" else "UP"
        eligible=[(index,e) for index,e in enumerate(events5)
                  if index not in used_m5_events
                  and sweep["at"]<e["at"]<=sweep["at"]+3600
                  and e["direction"]==target
                  and e["segment_start"]<=sweep["at"]<e["at"]]
        if eligible:
            index,confirmation=min(eligible,key=lambda item:(item[1]["at"],item[0]))
            used_m5_events.add(index)
            matched+=1
            by_side["SELL" if target=="DOWN" else "BUY"]+=1
            historical=next((g for g in m15_segments if g[0]["close_time"]<=sweep["at"]<=g[-1]["close_time"]),None)
            if historical:
                known=[b for b in historical if b["close_time"]<=sweep["at"]]
                v=calculate(known,period=14,as_of=sweep["at"],interval=900)
                if v["status"]=="OK":
                    vhf_evaluable+=1
                    if v["value"]>=0.4 and v["slope"]=="RISING":
                        vhf_passed+=1
                        poi=confirmation.get("poi")
                        confirmed={'sweep_close':sweep['at'],'confirmation_close':confirmation['at'],
                                   'side':'BUY' if target=='UP' else 'SELL',
                                   'poi':dict(poi) if poi is not None else None,
                                   'vhf_at_sweep':v['value']}
                        # This universe is emitted without reference to future POI touches.
                        confirmation_evidence.append(confirmed)
                        observation=observe_retest(confirmed,m5['bars'])
                        retest_observations.append(dict(observation,sweep_close=sweep['at'],
                                                       confirmation_close=confirmation['at'],side=confirmed['side']))
                        if poi is not None:
                            vhf_poi+=1
                        if observation['status']=='RETEST':
                            vhf_retouch+=1
                            retouch_evidence.append({'sweep_close':sweep['at'],
                                'confirmation_close':confirmation['at'],
                                'first_poi_touch_close':observation['entry_at'],'side':confirmed['side'],
                                'poi_low':poi['low'],'poi_high':poi['high'],'vhf_at_sweep':v['value']})
    return {"status":"EXPLORATORY_REAL_M15_M5_SEQUENCE_NOT_LSR02",
            "m15_sweeps":len(events15),"m5_bos_choch_events":len(events5),
            "unique_one_to_one_sweep_m5_matches":matched,
            "candidate_sides":by_side,
            "sweep_time_vhf_evaluable":vhf_evaluable,
            "sweep_time_vhf_research_passed":vhf_passed,
            "vhf_passed_with_m5_poi":vhf_poi,
            "vhf_passed_with_postconfirmation_poi_touch":vhf_retouch,
            "retouch_evidence":retouch_evidence,
            "confirmation_evidence":confirmation_evidence,"retest_observations":retest_observations,
            "vhf_period":14,"research_vhf_threshold":0.4,"unique_executed_trades":0,
            "h4_trend_verified":False,"retest_entry_verified":False,"poi_touch_research_evaluated":True,
            "vhf_filter_evaluated":True,"spread_and_execution_verified":False,
            "win_rate":None,"profit_usd":None,
            "warning":"M5 events assigned once; overlapping sweep windows remain research-only. No trade inference."}
if __name__=="__main__":
    root=Path("public_xau_bars")
    result=report(root)
    Path("public_xau_sequence_report.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))
