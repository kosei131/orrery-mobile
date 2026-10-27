"""ORRERY FX local MT5 dashboard. Windows-only, DEMO-only, NO order functions.
Start: py mt5_local_dashboard.py
Opens http://127.0.0.1:8765 on the SAME Windows PC. Not reachable from iPhone.
"""
import argparse
import json
import secrets
import sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit

PARSER = argparse.ArgumentParser(description='ORRERY FX local DEMO-only dashboard')
PARSER.add_argument('--test-data', action='store_true', help='Simulated data, no MT5 required')
ARGS = PARSER.parse_args()
if not ARGS.test_data:
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print('Install first: py -m pip install MetaTrader5')
        sys.exit(2)

HOST, PORT = "127.0.0.1", 8765
TOKEN = secrets.token_urlsafe(24)
HTML = """<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ORRERY MT5 Local</title>
<style>body{background:#0b0c10;color:#eee0c4;font:16px system-ui;margin:0;padding:20px}main{max-width:800px;margin:auto}h1{color:#ddb66e}section{background:#17181b;border:1px solid #806238;border-radius:12px;margin:12px 0;padding:16px}table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid #42372b;padding:9px;text-align:left}.muted{color:#bbb;font-size:13px}.big{font-size:25px;font-weight:700}button{background:#d4ae69;padding:10px;border:0;border-radius:8px}</style>
<main><h1>ORRERY FX · LOCAL MT5</h1><p class="muted">Windowsパソコン専用 · DEMO限定 · 読み取り専用 · 10秒ごとに更新 · 外部送信なし</p><section id="state">MT5接続を確認中...</section><section><div id="summary"></div></section><section><h3>POSITIONS</h3><table><thead><tr><th>Symbol</th><th>Side</th><th>Lot</th><th>P/L</th></tr></thead><tbody id="pos"></tbody></table></section><button id="refresh">今すぐ更新</button><p class="muted">この画面は同じWindows PCでのみ利用できます。iPhone同期は未実装です。</p></main>
<script>
const auth=location.hash.slice(1);history.replaceState({},'',location.pathname);
const $=id=>document.getElementById(id);
const fmt=(x,c)=>new Intl.NumberFormat('en-US',{style:'currency',currency:c||'USD'}).format(x);
function cell(tr,v){const td=document.createElement('td');td.textContent=String(v);tr.appendChild(td)}
async function refresh(){try{let r=await fetch('/api/snapshot',{headers:{'X-Orrery-Token':auth},cache:'no-store'});let j=await r.json();if(!r.ok)throw Error(j.error||'Connection failed');$('state').textContent=(j.status==='SIMULATED_TEST_DATA'?'⚠️ TEST DATA — NOT REAL MT5 | ':'DEMO | ')+j.broker_server+' | ACCOUNT ****'+j.account_last4+' | '+j.checked_at_utc;
$('summary').textContent='BALANCE: '+fmt(j.balance,j.currency)+'　 EQUITY: '+fmt(j.equity,j.currency)+'　 FREE MARGIN: '+fmt(j.margin_free,j.currency)+'　 DEALS (7d): '+j.history_7d_count;
$('pos').replaceChildren();for(let p of j.positions){let tr=document.createElement('tr');[p.symbol,p.side,p.lots,fmt(p.pnl,j.currency)].forEach(v=>cell(tr,v));$('pos').appendChild(tr)}
}catch(e){$('state').textContent='ERROR: '+e.message;$('summary').textContent='';$('pos').replaceChildren()}}
$('refresh').onclick=refresh;refresh();setInterval(refresh,10000);
</script></html>"""

def snapshot():
    if ARGS.test_data:
        return dict(status='SIMULATED_TEST_DATA', broker_server='SIMULATED-NO-BROKER',
            account_last4='0000', currency='USD', balance=10000.00, equity=10024.50,
            margin_free=9500.00, history_7d_count=3, checked_at_utc=datetime.now(timezone.utc).isoformat(),
            positions=[dict(symbol='XAUUSD-TEST', side='BUY', lots=0.01, pnl=24.50)])
    if not mt5.initialize():
        raise RuntimeError("MT5 not available: " + str(mt5.last_error()))
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
        return dict(status="READ_ONLY_DEMO", broker_server=account.server,
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
        # Prevent third-party web pages from accessing local MT5 data.
        if self.headers.get("Origin") or self.headers.get("Sec-Fetch-Site") in ("cross-site","same-site"):
            self.send_error(403)
            return
        if path == "/":
            self.respond(200, HTML, "text/html; charset=utf-8")
        elif path == "/api/snapshot":
            if not secrets.compare_digest(self.headers.get("X-Orrery-Token",""), TOKEN):
                self.respond(403, json.dumps({"error":"Unauthorized"}), "application/json")
                return
            try:
                self.respond(200,json.dumps(snapshot(),ensure_ascii=False),"application/json")
            except Exception as exc:
                self.respond(503,json.dumps({"error":str(exc)}),"application/json")
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
