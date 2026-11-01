# 指定カレンダーによる05の休場/欠損検査

2026-10-29（ハワイ）。実ブローカーの営業時刻は今回取得していない。
通常のcalculateは従来どおり時間間隔の欠損で停止する。
明示した証拠と保持pinがある研究モードだけ、指定CLOSED区間の空きを受け付ける。
既存calendar_minutesを再利用し、週末/日次休止の推測、架空足の補完は行わない。
Amplitude/ATR100は実際の足の本数で進め、休場明けの価格差もTrue Rangeへ反映する。

```python
from lsr05_halftrend import calculate
result = calculate(closed_bars, as_of=known_time, interval=900, enabled=True,
    symbol='XAUUSD', data_source='documented_feed',
    calendar_evidence=evidence, expected_calendar_sha256=retained_evidence_pin)
```

## 証拠と時刻

evidenceはsymbol、data_source、known_at_utc、source_document_sha256、calendarを持つ。
calendarは既存形式のsourceとintervals。各区間はstart_utc/end_utc/state。
明示UTCのISO時刻、連続・非重複区間、OPEN/CLOSEDのみ、M5/M15グリッドに合う期間端点、
最大1年の範囲を要求する。sourceは資料の説明/URL等、document hashは保持する元資料のpin。
元資料、銘柄、業者、対象日、サーバー時刻/UTC換算、祝日等は接続側で別途確認する。
hashやsourceラベルだけでブローカーの真正性は証明できない。

known_at_utcは、その営業表を判断に使えた時刻として検査期間の開始以前を要求する。
後から公表された休場情報を過去の判断へ遡らせない。
最初のAPIは検査期間全体がas_of以前であることを要求する。
未来予定を含む営業表は、当時既知だった情報のまま今回の検査期間へ切り出す。
銘柄/データ元が違う営業表、UNKNOWN、穴/重複、時刻不明、pin不一致は停止する。

lsr05_session_clock.evidence_sha256はcanonical JSONのhashを返す。
受領時に別途保持したpinとの照合が必要で、評価時に同じ入力から再計算するだけでは
証拠の置換を検出できない。

## 検査の意味

audit_close_timesは価格ではなく、営業表から期待する足終点と実際の足終点を比較する。
営業中の足が欠ける、休場/期間外の終点がある場合はBLOCKED_SESSION_HISTORY。
一致しても足内部のM1/ティック完全性は未証明。OHLC値はHalfTrend入口で別に検査する。
一部だけOPENな足も既存カレンダー処理と同じく観測対象だが、
部分足の集約仕様が実際のブローカー足と同じかは別途確認する。

計算結果に証拠と監査結果を付け、observerも時間監査を再計算してから空きを受け付ける。
元資料・公開時刻・出所・開始点を識別し、同じ資料の期間末尾を延長しただけなら
別指標へ切り替えず、未来足追加時の変更検出を維持する。
観測イベントに証拠hashを記録し、保存APIではsnapshot全体を保存する。

observerコードが変わるため、旧保存ストアを同じ実装として自動復元しない。
旧データ/コード/pinを保持し、新観測は新規ストアへ保存する。自動移行は未実装。

calendar_broker_verified / ohlc_completeness_verified / market_edge_verified /
execution_allowedはfalse。指定資料に整合する研究上の時間検査に限る。
MT5営業表の実取得、過去6か月の例外日確認、実市場利益の検証は未実施。
既存03/04、構造SL、口座リスク、発注設定は変更しない。
