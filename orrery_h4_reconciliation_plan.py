"""Offline pinned 19-slot intake plan. Does not import MT5 or place orders."""
import argparse,json,hashlib
from pathlib import Path
from datetime import datetime,timedelta,timezone

# UTC H4 closing dates from artifact 13037635338, deduplicated across candidates.
CLOSE_DATES=('2026-08-24','2026-08-26','2026-08-27','2026-08-28',
 '2026-09-03','2026-09-04','2026-09-07','2026-09-08','2026-09-09',
 '2026-09-10','2026-09-11','2026-09-14','2026-09-15','2026-09-16',
 '2026-09-17','2026-09-18','2026-09-21','2026-09-22')
SOURCE_ARTIFACT_SHA256='fd2ebec3e9ce290512169a7a09c47daf725b9a880d903dbc0cf09aced9756bd2'


def build_plan():
    ends=[datetime.fromisoformat(d).replace(tzinfo=timezone.utc) for d in CLOSE_DATES]
    ends.append(datetime(2026,9,7,20,tzinfo=timezone.utc));ends.sort()
    slots=[];chunks=[]
    for index,end in enumerate(ends):
        start=end-timedelta(hours=4)
        slots.append(dict(id=index,start_utc=start.isoformat(),end_utc_exclusive=end.isoformat(),
            expected_m1_count=None,broker_session_verified=False))
        for n in range(24):
            a=start+timedelta(minutes=10*n)
            chunks.append(dict(id=len(chunks),slot_id=index,start_utc=a.isoformat(),
                               end_utc_exclusive=(a+timedelta(minutes=10)).isoformat()))
    return dict(status='OFFLINE_INTAKE_PLAN_ONLY',symbol='XAUUSD',slots=slots,tick_chunks=chunks,
        source_artifact_sha256=SOURCE_ARTIFACT_SHA256,
        source_revision='3ceb5b3053fc0244048ac3fad4dd2dcc0df52754',
        demo_required=True,terminal_connected=False,history_acquired=False,
        broker_symbol_mapping_verified=False,broker_calendar_verified=False,
        backtest_ready=False,execution_allowed=False)


def save_plan(output):
    plan=build_plan();raw=(json.dumps(plan,sort_keys=True,indent=2)+'\n').encode()
    root=Path(output);root.mkdir(parents=False,exist_ok=False)
    with (root/'request.json').open('xb') as f:f.write(raw)
    receipt=dict(status='PLAN_SAVED_NOT_EXECUTED',request_sha256=hashlib.sha256(raw).hexdigest(),
                 slots=len(plan['slots']),tick_chunks=len(plan['tick_chunks']),execution_allowed=False)
    with (root/'receipt.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2)
    return receipt

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args=parser.parse_args();print(json.dumps(save_plan(args.output)))
