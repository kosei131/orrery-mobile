"""Generate a deterministic SYNTHETIC example viewer. No account/market inputs."""
import json
from pathlib import Path
import sys
from test_lsr02_paths import fixture, run
from lsr02_replay import replay


def build():
    cases=[]
    for side in ('BUY','SELL'):
        for scenario in ('normal','expiry','stop'):
            h,f,m=fixture(side=='SELL')
            if scenario=='stop':
                m[-1]['high' if side=='SELL' else 'low']=21 if side=='SELL' else 9
            trace=run(h,f,m,lifetime=2400 if scenario=='expiry' else 6000)
            cases.append(dict(name=f'{side} / {scenario}',mode='構造判定のみ（比較用）',trace=trace))
    for side in ('BUY','SELL'):
        for change in (True,False):
            h,f,m=fixture(side=='SELL')
            while m[-1]['close_time']<116400:
                m.append(dict(m[-1],close_time=m[-1]['close_time']+300))
            if change:
                b=dict(open=14,high=15,low=10,close=11,close_time=115200)
                if side=='SELL': b.update(open=16,high=20,low=15,close=19)
                h.append(b)
            trace=replay('XAUUSD',h,f,m,as_of=m[-1]['close_time'],buffer=.1,lifetime=60000,left=1,right=1,
                         regime_config=dict(lookback=7,trend_efficiency=.2,range_efficiency=.1))
            cases.append(dict(name=side+' / '+('regime_changed' if change else 'regime_stale'),mode='環境フィルターあり（実験）',trace=trace))
    payload=json.dumps(cases,ensure_ascii=True,separators=(',',':'))
    return '''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ORRERY · LSR-02検証</title><style>
:root{color-scheme:dark;font:15px system-ui;background:#090b10;color:#eee7d9}*{box-sizing:border-box}main{max-width:960px;margin:auto;padding:20px}h1,a,h2{color:#d8b56e}section{padding:18px;border:1px solid #5f4a2b;border-radius:12px;background:#15171d;margin:16px 0}p{line-height:1.8}.warning{color:#ffd18b}select{font:inherit;padding:12px;background:#24252b;color:#fff;max-width:100%}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;white-space:nowrap}th,td{padding:12px 8px;text-align:left;border-bottom:1px solid #3e3a31}.note{color:#b4ac9e;font-size:13px}output{display:block;margin-top:14px;font-size:18px}caption{text-align:left;padding:10px 0}</style></head><body><main><a href="fx.html">← FX</a><h1>LSR-02 · 判定経過の検証</h1>
<section><strong class="warning">SYNTHETIC TEST DATA / 合成データ専用</strong><p>実相場・MT5口座・バックテスト成績ではありません。価格と時刻はテスト用です。READY生成・注文・ロット計算は無効です。</p><label for="scenario">検証ケース</label><br><select id="scenario"></select><output id="summary" role="status"></output><p id="detail"></p></section>
<section class="scroll"><table><caption>各確定足で利用可能だった情報による判定</caption><thead><tr><th scope="col">確定時刻（UTC）</th><th scope="col">方向</th><th scope="col">状態</th><th scope="col">SL基準</th><th scope="col">POI範囲</th><th scope="col">相場環境</th><th scope="col">環境判定の理由</th><th scope="col">停止理由</th></tr></thead><tbody id="rows"></tbody></table></section>
<section><h2>状態の読み方</h2><p>SWEEP：4H方向と15mの流動性取り込みが一致。<br>CONFIRM：後続5mで構造変化とPOIを確認。<br>RETEST：さらに後の5m足がPOIに重なる。まだエントリー許可ではありません。<br>INVALID：期限切れ、SL基準への到達、または相場環境の変化。</p><p class="note">normalは構造確認と再到達、expiryは有効期限境界、stopは再到達後のSL接触を検証します。ニュース・実スプレッド・口座リスクを取得していないため、全ケースで取引準備はブロックしています。regime_changedは環境判定の不一致、regime_staleは古い4Hデータによる停止を検証します。環境分類の閾値は合成テスト専用で、実運用向けに調整されていません。2.6分析は判定に使用していません。</p></section>
<p class="note">この画面はPython再生処理の固定結果を表示します。現在価格の監視や新規シグナル生成は行いません。入力保存・外部通信なし。</p></main><script>
'use strict';
const cases=PAYLOAD;
const $=id=>document.getElementById(id);
const labels={EXPIRED:'有効期限に到達',STOP_TOUCHED:'SL基準に接触',HTF_CONTEXT_INVALID:'4H方向が無効',UP:'上昇',DOWN:'下降',UNKNOWN:'判定不能',RANGE_CANDIDATE:'レンジ候補',STRUCTURE_AND_EFFICIENCY_AGREE:'構造と方向効率が一致',CONFLICTING_EVIDENCE:'判断材料が不一致',INSUFFICIENT_CONFIRMED_SWINGS:'確定スイング不足',STALE_DATA:'4Hデータが古い',REGIME_REVIEW_REQUIRED:'環境変化：候補停止・再確認が必要'};
for(let i=0;i<cases.length;i++){const o=document.createElement('option');o.value=String(i);o.textContent=cases[i].name;$('scenario').appendChild(o);}
function render(){const c=cases[Number($('scenario').value)||0];$('rows').replaceChildren();for(const e of c.trace){const tr=document.createElement('tr');for(const value of [new Date(e.at*1000).toISOString(),e.side,e.state,e.stop.toFixed(3),e.poi?e.poi.map(x=>x.toFixed(3)).join(' – '):'未確定',labels[e.regime]||'未適用',labels[e.regime_reason]||e.regime_reason||'比較用：環境分類なし',labels[e.reason]||(e.state==='INVALID'?'このケースの期限切れ／SL接触':'—')]){const td=document.createElement('td');td.textContent=value;tr.appendChild(td);}$('rows').appendChild(tr);}
const last=c.trace.at(-1);$('summary').textContent=c.name+' · 最終状態 '+(last?.state||'候補なし');$('detail').textContent=c.mode+' / '+(last?.reason==='REGIME_REVIEW_REQUIRED'?'候補停止後は同じ再生内で再開しません。 ':'')+'取引準備：BLOCKED / ニュース・スプレッド・口座条件は未検証';}
$('scenario').addEventListener('change',render);render();
</script></body></html>
'''.replace('PAYLOAD',payload)

if __name__=='__main__':
    target=Path('lsr-viewer.html');content=build()
    if '--check' in sys.argv:
        if not target.exists() or target.read_text(encoding='utf-8')!=content:
            raise SystemExit('Viewer is stale; run python build_lsr_view.py')
        print('PASS: viewer matches synthetic replay outputs')
    else:target.write_text(content,encoding='utf-8')
