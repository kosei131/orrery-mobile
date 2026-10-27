"""ORRERY FX local MT5 dashboard. Windows-only, DEMO-only, NO order functions.
Start: py mt5_local_dashboard.py
Opens http://127.0.0.1:8765 on the SAME Windows PC. Not reachable from iPhone.
"""
import argparse
import json
import secrets
import sys
from math import isfinite
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit

PARSER = argparse.ArgumentParser(description='ORRERY FX local DEMO-only dashboard')
PARSER.add_argument('--test-data', action='store_true', help='Simulated data, no MT5 required')
ARGS = argparse.Namespace(test_data=False)
mt5 = None

HOST, PORT = "127.0.0.1", 8765
TOKEN = secrets.token_urlsafe(24)
HTML = """<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ORRERY MT5 Local</title>
<style>body{background:#0b0c10;color:#eee0c4;font:16px system-ui;margin:0;padding:20px}main{max-width:800px;margin:auto}h1{color:#ddb66e}section{background:#17181b;border:1px solid #806238;border-radius:12px;margin:12px 0;padding:16px}table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid #42372b;padding:9px;text-align:left}.muted{color:#bbb;font-size:13px}.big{font-size:25px;font-weight:700}button{background:#d4ae69;padding:10px;border:0;border-radius:8px}</style>
<main><h1>ORRERY FX · LOCAL MT5</h1><p class="muted">Windowsパソコン専用 · DEMO限定 · 読み取り専用 · 1秒間隔で更新要求（取得中は待機） · 外部送信なし</p><section id="state">MT5接続を確認中...</section><section><div id="summary"></div></section><section><h3>MT5 DEMO · BID / ASK</h3><p class="muted">ブローカー配信の最終ティック。ローソク足チャートではありません。価格時刻が10秒超過・未来の場合は利用不可。未対応銘柄は代替価格を使いません。</p><div id="quotes" style="white-space:pre-line">未取得</div></section><section><h3>MT5 DEMO · 確定足チャート</h3><p class="muted">内部取得最大100本・表示は直近70本・未確定足なし。価格表示は1秒間隔で取得要求しますが、確定足の追加は選択時間足ごとです。欠損・古い履歴は描画しません。LSR判定とは未接続。</p><label for="chartFrame">時間足</label><select id="chartFrame"><option value="5m">5分足</option><option value="15m">15分足</option><option value="4H">4時間足</option></select><div id="charts"></div></section><section><h3>POSITIONS</h3><table><thead><tr><th>Symbol</th><th>Side</th><th>Lot</th><th>P/L</th></tr></thead><tbody id="pos"></tbody></table></section><button id="refresh">今すぐ更新</button><p class="muted">この画面は同じWindows PCでのみ利用できます。iPhone同期は未実装です。</p></main>
<script>
const auth=location.hash.slice(1);history.replaceState({},'',location.pathname);
const $=id=>document.getElementById(id);
const fmt=(x,c)=>new Intl.NumberFormat('en-US',{style:'currency',currency:c||'USD'}).format(x);
let lastChartData={charts:[]};
function drawCharts(j){lastChartData=j;const host=$('charts');host.replaceChildren();if(j.status==='SIMULATED_TEST_DATA'){host.textContent='SIMULATED TEST DATA — 市場チャート未接続';return}for(const c of j.charts||[]){if(c.timeframe!==($('chartFrame').value||'5m'))continue;const title=document.createElement('p');title.textContent=c.symbol+' / '+c.timeframe+' / '+c.status+(c.last_close_utc?' / '+c.last_close_utc:'');host.appendChild(title);if(c.status!=='CLOSED_BARS_AVAILABLE'||!Array.isArray(c.bars)||c.bars.length<2||c.bars.length>100)continue;const bars=c.bars.slice(-70);if(!bars.every(b=>['open','high','low','close'].every(k=>Number.isFinite(b[k])&&b[k]>0)&&b.low<=Math.min(b.open,b.close)&&b.high>=Math.max(b.open,b.close)))continue;const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 700 220');svg.setAttribute('role','img');svg.setAttribute('aria-label',c.symbol+' '+c.timeframe+' 確定足');svg.style.width='100%';const low=Math.min(...bars.map(b=>b.low)),high=Math.max(...bars.map(b=>b.high)),range=Math.max(high-low,.000001),y=v=>10+200*(high-v)/range,step=680/bars.length;bars.forEach((b,i)=>{const color=b.close>=b.open?'#4db59a':'#ce424d',x=10+i*step;const line=document.createElementNS(ns,'line');for(const [k,v]of Object.entries({x1:x+step*.4,x2:x+step*.4,y1:y(b.high),y2:y(b.low),stroke:color}))line.setAttribute(k,String(v));svg.appendChild(line);const rect=document.createElementNS(ns,'rect');for(const [k,v]of Object.entries({x,y:Math.min(y(b.open),y(b.close)),width:step*.8,height:Math.max(1,Math.abs(y(b.open)-y(b.close))),fill:color}))rect.setAttribute(k,String(v));svg.appendChild(rect)});host.appendChild(svg)}}
function cell(tr,v){const td=document.createElement('td');td.textContent=String(v);tr.appendChild(td)}
let refreshing=false;
async function refresh(){if(refreshing)return;refreshing=true;$('refresh').disabled=true;const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),5000);try{let r=await fetch('/api/snapshot',{headers:{'X-Orrery-Token':auth},cache:'no-store',signal:controller.signal});let j=await r.json();if(!r.ok)throw Error(j.error||'Connection failed');$('state').textContent=(j.status==='SIMULATED_TEST_DATA'?'⚠️ TEST DATA — NOT REAL MT5 | ':'DEMO | ')+j.broker_server+' | ACCOUNT ****'+j.account_last4+' | '+j.checked_at_utc;
$('summary').textContent='BALANCE: '+fmt(j.balance,j.currency)+'　 EQUITY: '+fmt(j.equity,j.currency)+'　 FREE MARGIN: '+fmt(j.margin_free,j.currency)+'　 DEALS (7d): '+j.history_7d_count;
$('quotes').textContent=j.status==='SIMULATED_TEST_DATA'?'SIMULATED TEST DATA — 市場価格は接続しません':(j.quotes||[]).map(q=>q.symbol+' | '+q.status+(q.status==='AVAILABLE'?' | Bid '+q.bid+' / Ask '+q.ask+' / Spread '+q.spread+' | '+q.tick_at_utc:'')).join('\\n');
drawCharts(j);
$('pos').replaceChildren();for(let p of j.positions){let tr=document.createElement('tr');[p.symbol,p.side,p.lots,fmt(p.pnl,j.currency)].forEach(v=>cell(tr,v));$('pos').appendChild(tr)}
}catch(e){$('state').textContent='ERROR: '+e.message;$('summary').textContent='';$('quotes').textContent='取得失敗：価格は利用不可';lastChartData={charts:[]};$('charts').replaceChildren();$('pos').replaceChildren()}finally{clearTimeout(timeout);refreshing=false;$('refresh').disabled=false}}
$('chartFrame').onchange=()=>drawCharts(lastChartData);
$('refresh').onclick=refresh;refresh();setInterval(refresh,1000);
</script></html>"""

def read_quotes(now):
    quotes=[]
    for symbol in ('XAUUSD','USDJPY'):
        item=dict(symbol=symbol,status='UNAVAILABLE',source='MT5_DEMO_BROKER_TICK')
        try:
            tick=mt5.symbol_info_tick(symbol)
            if tick is not None:
                vals=(tick.bid,tick.ask,tick.time_msc)
                if any(type(v) not in (int,float) or not isfinite(v) for v in vals) or not 0<tick.bid<=tick.ask:
                    item['status']='INVALID'
                else:
                    age=now.timestamp()-tick.time_msc/1000
                    if not 0<=age<=10:
                        item['status']='STALE_OR_FUTURE'
                    else:
                        item.update(status='AVAILABLE',bid=tick.bid,ask=tick.ask,spread=tick.ask-tick.bid,
                            tick_at_utc=datetime.fromtimestamp(tick.time_msc/1000,timezone.utc).isoformat())
        except Exception:
            pass  # No terminal error details or synthetic fallback.
        quotes.append(item)
    return quotes

def read_closed_charts(now):
    charts=[]
    for symbol in ('XAUUSD','USDJPY'):
        for label,enum_name,seconds in (('5m','TIMEFRAME_M5',300),('15m','TIMEFRAME_M15',900),('4H','TIMEFRAME_H4',14400)):
            item=dict(symbol=symbol,timeframe=label,status='UNAVAILABLE',bars=[])
            try:
                rates=mt5.copy_rates_from_pos(symbol,getattr(mt5,enum_name),1,100)
                if rates is not None and 2<=len(rates)<=100:
                    bars=[]
                    for row in rates:
                        b={k:float(row[k]) for k in ('open','high','low','close')}
                        t=float(row['time']);closed=t+seconds
                        if not all(isfinite(v) for v in (*b.values(),t)) or t%seconds or closed>now.timestamp() or not 0<b['low']<=min(b['open'],b['close'])<=max(b['open'],b['close'])<=b['high']:
                            raise ValueError('Invalid bar')
                        if bars and t-bars[-1]['time']!=seconds:
                            raise ValueError('Discontinuous bars')
                        bars.append(dict(time=t,**b))
                    if now.timestamp()-(bars[-1]['time']+seconds)>=seconds:
                        item['status']='STALE'
                    else:
                        item.update(status='CLOSED_BARS_AVAILABLE',bars=bars,
                            last_close_utc=datetime.fromtimestamp(bars[-1]['time']+seconds,timezone.utc).isoformat())
            except Exception:
                pass
            charts.append(item)
    return charts

def snapshot():
    if ARGS.test_data:
        return dict(status='SIMULATED_TEST_DATA', broker_server='SIMULATED-NO-BROKER',
            account_last4='0000', currency='USD', balance=10000.00, equity=10024.50,
            margin_free=9500.00, history_7d_count=3, checked_at_utc=datetime.now(timezone.utc).isoformat(),
            positions=[dict(symbol='XAUUSD-TEST', side='BUY', lots=0.01, pnl=24.50)])
    if not mt5.initialize():
        raise RuntimeError("MT5 not available; open the DEMO terminal and retry")
    try:
        account = mt5.account_info()
        if account is None:
            raise RuntimeError("No active MT5 account")
        if account.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
            raise RuntimeError("SAFETY STOP: DEMO accounts only")
        positions = mt5.positions_get()
        end = datetime.now(timezone.utc)
        history = mt5.history_deals_get(end - timedelta(days=7), end)
        if positions is None or history is None:
            raise RuntimeError("Unable to read MT5 account data")
        quotes=read_quotes(datetime.now(timezone.utc))
        charts=read_closed_charts(datetime.now(timezone.utc))
        current=mt5.account_info()
        if current is None or current.trade_mode!=mt5.ACCOUNT_TRADE_MODE_DEMO or current.login!=account.login or current.server!=account.server:
            raise RuntimeError('Account changed during read; discard snapshot')
        return dict(charts=charts,quotes=quotes,status="READ_ONLY_DEMO", broker_server=account.server,
            account_last4=str(account.login)[-4:], currency=account.currency,
            balance=round(account.balance,2), equity=round(account.equity,2),
            margin_free=round(account.margin_free,2), history_7d_count=len(history),
            checked_at_utc=end.isoformat(),
            positions=[dict(symbol=p.symbol,side="BUY" if p.type==mt5.POSITION_TYPE_BUY else "SELL",
                lots=p.volume,pnl=round(p.profit,2)) for p in positions])
    finally:
        mt5.shutdown()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        # Reject DNS rebinding and requests addressed through non-loopback hosts.
        if self.headers.get("Host", "") not in ("127.0.0.1:8765", "localhost:8765"):
            self.send_error(403)
            return
        # Prevent third-party web pages from accessing local MT5 data.
        if self.headers.get("Origin") or self.headers.get("Sec-Fetch-Site") in ("cross-site","same-site"):
            self.send_error(403)
            return
        if path == "/":
            self.respond(200, HTML, "text/html; charset=utf-8")
        elif path == "/api/snapshot":
            if not secrets.compare_digest(self.headers.get("X-Orrery-Token", "").encode("utf-8"), TOKEN.encode("ascii")):
                self.respond(403, json.dumps({"error":"Unauthorized"}), "application/json")
                return
            try:
                self.respond(200,json.dumps(snapshot(),ensure_ascii=False),"application/json")
            except Exception:
                # Never return terminal errors, account details or exception text.
                self.respond(503, json.dumps({"error": "MT5 data unavailable. Check the connected DEMO terminal."}), "application/json")
        else:
            self.send_error(404)
    def respond(self, status, data, content_type):
        data = data.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type",content_type)
        self.send_header("Content-Length",str(len(data)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("Content-Security-Policy","default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'")
        self.end_headers()
        self.wfile.write(data)
    def log_message(self, fmt, *args):
        pass

if __name__ == "__main__":
    ARGS = PARSER.parse_args()
    if not ARGS.test_data:
        try:
            import MetaTrader5 as mt5
        except ImportError:
            print('Install first: py -m pip install MetaTrader5')
            sys.exit(2)
    server = HTTPServer((HOST,PORT),Handler)
    print("ORRERY FX LOCAL — " + ("SIMULATED TEST DATA" if ARGS.test_data else "DEMO READ-ONLY"))
    print("Open in Windows browser: http://%s:%s/#%s" % (HOST,PORT,TOKEN))
    print("Ctrl+C to stop; keep this address private. NO ORDERS, NO CLOUD SYNC.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        server.server_close()
