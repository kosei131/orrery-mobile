# 05確定サイン・状態線の観測アダプター

`lsr05_observation.HalfTrendObserver` は、既存SignalJournalを注入して使う独立研究API。
HalfTrend計算は作り直さず、前工程のsnapshotを受け取る。
既存03/04のサイン判定・照合・注文設定は変更しない。
このファイルとテストはGPL-3.0表示付き。原典とライセンスはresearch_refs/halftrendに同梱。

```python
from lsr04_signal_journal import SignalJournal
from lsr05_halftrend import calculate
from lsr05_observation import HalfTrendObserver

journal05 = SignalJournal()  # 04との混在を避けて05専用にする
monitor = HalfTrendObserver(journal05)
snapshot = calculate(closed_bars, as_of=known_time, interval=300, enabled=True)
observation = monitor.observe(snapshot, symbol='XAUUSD', observed_at=received_time,
    data_source='documented_feed', implementation_version='retained_code_revision')
```

既存アプリ/MT5ループへの自動組込みは行っていない。PCで動作中という意味ではない。
アダプター自体は標準ライブラリのみ。既存journalのobserveメソッドを明示的に呼び出す。

## 保存する意味と時刻

- 原典ソース版/ハッシュ、Amplitude、Deviation、足間隔、履歴開始点、データ元、実装版を識別。
- 同じ設定・同じ足を再観測し、サインだけでなく状態線/ATRチャネルの変化も記録する。
- 変更前の観測を残す。変更があっても過去時点の判断を新しいサインへ置換しない。
- signal_eventsのclosed_atは足の確定時刻、observed_atはcallerが受信した時刻。
  過去チャートを今読み込んだ場合、observed_atを過去の足時刻へ戻さない。
- 同一内容の再読込は新イベントに増やさない。観測継続はlast_seen_scopesへ別記録。
  これは観測APIにsnapshotが届いた情報であり、workerやMT5通信のheartbeat証明ではない。
- ウォームアップ中は内部値を記録するが、既存journalへ確定NONE/BUY/SELLを送らない。
- Deviation/Amplitudeや履歴開始点が違う場合は別識別子として比較する。
  異なる条件同士をリペイント検査として混同しない。

configurationの識別子に全入力ハッシュは使わない。
未来足を足すたびに別指標となって変更検出できなくなるのを避けるため。
各イベントには、その時点のinput_sha256を証拠として保存する。
implementation_versionは保持したコード版をcallerが明示する。自動の実行証明ではない。

## 失敗時・上限

未来の足・未確定な転換・不正チャネル・設定不整合・観測時刻/履歴終点の後退は停止。
全行の事前検査とイベント容量検査を行ってから既存journalへ渡す。
上限は既定10万の新規/変更イベント。勝手に古い観測を捨てず、上限で停止する。
保存してから新しいセッションを開始する場合、観測の断絶を継続監視の証拠にしない。
注入先journalと本アダプターの間に永続トランザクションはない。
外部journal側の例外・プロセス終了時の原子的な保存は今回の保証外。

この観測API自体の記録はメモリー上。独立した保存/再生APIを
lsr05_observation_store.pyへ追加した（LSR05_OBSERVATION_STORE_JA.md参照）。
MT5ループから自動取得・保存する接続は未実装。
返したレコードを書き換えても、保持中の履歴が書き換わらないようコピーを返す。

## 検証の境界

値やサインの変更は、フィード訂正・履歴の再計算・実装変更等でも起きる。
検出した変更だけで、元インジケーターの欠陥や不正なリペイントと断定しない。
未観測期間の変化、瞬間的な未確定サイン、与えられなかったsnapshotは検出できない。
観測変化が0でも不リペイントの証明にはならない。

既存as-of照合へ渡す際は、このアダプターの05専用signal_eventsと設定識別子を使い、
候補成立時までにobserved_atが到達しているものだけを使用する。
03/04/05のA/B/C/D比較へ自動結線する部分は未実装。
TradingView/MT5で同一OHLCを使った数値比較、実市場での観測は未実施。
nonrepainting_verified / market_edge_verified / execution_allowedはfalseのまま。
