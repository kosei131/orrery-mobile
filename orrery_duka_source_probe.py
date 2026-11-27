"""One anonymous public hourly archive probe, isolated from all trading data.
No paid S3 route, credentials, redirects, price scaling, orders or account PnL.
"""
import argparse
import hashlib
import json
import lzma
import struct
import urllib.error
import urllib.request
from datetime import datetime,timedelta,timezone
from math import isfinite
from pathlib import Path

MAX_COMPRESSED=30_000_000
MAX_DECODED=40_000_000


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise ValueError('Redirect refused; anonymous exact public endpoint only')


def fetch(url):
    # build_opener preserves the normal proxy and TLS trust configuration.
    opener=urllib.request.build_opener(NoRedirect())
    request=urllib.request.Request(url,headers={'User-Agent':'ORRERY-FX-research/1.0'})
    with opener.open(request,timeout=30) as response:
        if response.geturl()!=url:raise ValueError('Unexpected final URL')
        return response.read(MAX_COMPRESSED+1)


def validate(raw):
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_COMPRESSED:
        raise ValueError('Nonempty bounded compressed archive required')
    decoder=lzma.LZMADecompressor(memlimit=64*1024*1024)
    decoded=decoder.decompress(raw,max_length=MAX_DECODED+1)
    if (not decoded or len(decoded)>MAX_DECODED or not decoder.eof or decoder.unused_data
            or len(decoded)%20):
        raise ValueError('Bounded single-stream 20-byte record archive required')
    prior=-1;duplicates=0;first=None
    for offset in range(0,len(decoded),20):
        milliseconds,ask,bid,av,bv=struct.unpack_from('>IIIff',decoded,offset)
        if not 0<=milliseconds<3_600_000 or milliseconds<prior:
            raise ValueError('Out-of-hour or unordered tick timestamp')
        if not ask>=bid>0:raise ValueError('Nonpositive or inverted prices')
        if not all(isfinite(v) and v>=0 for v in (av,bv)):
            raise ValueError('Finite nonnegative volumes required')
        duplicates+=milliseconds==prior;first=milliseconds if first is None else first
        prior=milliseconds
    return dict(raw_sha256=hashlib.sha256(raw).hexdigest(),
        decoded_sha256=hashlib.sha256(decoded).hexdigest(),decoded_bytes=len(decoded),
        tick_count=len(decoded)//20,first_offset_msc=first,last_offset_msc=prior,
        repeated_timestamp_pairs=duplicates,price_scale_verified=False)


def probe(hour,symbol,out,*,now,download=fetch):
    if (not isinstance(hour,datetime) or hour.utcoffset()!=timedelta(0)
            or hour.minute or hour.second or hour.microsecond or symbol not in ('XAUUSD','USDJPY')
            or not isinstance(now,datetime) or now.utcoffset()!=timedelta(0)
            or hour+timedelta(hours=1)>=now):
        raise ValueError('Completed whole UTC hour and supported symbol required')
    out=Path(out);out.mkdir(parents=False,exist_ok=False)
    url=(f'https://datafeed.dukascopy.com/datafeed/{symbol}/'
         f'{hour.year:04d}/{hour.month-1:02d}/{hour.day:02d}/{hour.hour:02d}h_ticks.bi5')
    report=dict(symbol=symbol,hour_utc=hour.isoformat(),source_url=url,
        source='DUKASCOPY_ANONYMOUS_HOURLY_ARCHIVE_INDEPENDENT_RESEARCH',
        request_started_at_utc=now.isoformat(),execution_allowed=False,backtest_complete=False,
        source_is_user_mt5=False,merged_with_getdata=False,paid_route_used=False,
        broker_costs_verified=False,actual_profit_usd=None)
    try:
        raw=download(url);report.update(validate(raw))
        with (out/'source.bi5').open('xb') as stream:stream.write(raw)
        report['status']='RAW_TICKS_VALIDATED_SCALE_AND_COVERAGE_UNVERIFIED'
    except (ValueError,lzma.LZMAError,urllib.error.URLError,TimeoutError,OSError) as exc:
        report.update(status='BLOCKED_SOURCE_FETCH_OR_VALIDATION',error_type=type(exc).__name__)
        if isinstance(exc,urllib.error.HTTPError):report['http_status']=exc.code
    with (out/'manifest.json').open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n')
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hour',default='2026-10-22T12:00:00+00:00')
    parser.add_argument('--symbol',choices=('XAUUSD','USDJPY'),default='XAUUSD')
    parser.add_argument('--out',default='duka_source_sample',type=Path)
    a=parser.parse_args(argv)
    r=probe(datetime.fromisoformat(a.hour.replace('Z','+00:00')),a.symbol,a.out,
            now=datetime.now(timezone.utc))
    print(json.dumps(r))
    return 0 if r['status']=='RAW_TICKS_VALIDATED_SCALE_AND_COVERAGE_UNVERIFIED' else 2

if __name__=='__main__':raise SystemExit(main())
