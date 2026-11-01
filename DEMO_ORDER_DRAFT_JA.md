# デモ注文案の固定・再照合

lsr04_demo_order_draftはオフライン検証専用。MT5/Dotsへ接続せず、注文APIを呼ばない。
EntryはBUYでAsk、SELLでBid、SLは既存の構造SL計算、TPは指定した水準を維持する。
既存risk_planを再利用し、3連敗等の停止条件を維持。ロット上下限・数量ステップ、
提供された1ロットSL損失額×数量が計画リスク内か、実数量で費用込みRRが2以上か確認。

口座・仕様のローカル識別token、価格、ロット、SL/TP、リスク前提をhashで固定。
quote時刻から5秒以内に限り、再照合で口座・価格・仕様・リスク条件が変われば拒否。
ハッシュ一致は真正性証明ではない。snapshotや1ロット損失額は呼出側の提供値であり、
実MT5から取得したことや、そのSLに対する計算額であることを本モジュールは認証しない。
broker_snapshot_authenticated=False、broker_stops_and_margin_checked=False。

最小SL距離、freeze level、証拠金、取引時間、fill policy、冪等性、約定結果照合、
デモ口座の実API再確認、取引送信はいずれも後工程。
DRAFT_RECHECKEDでも発注許可ではない。execution_allowedは常にFalse。
Dots連携・実Windowsでの動作・収益性は未検証。既存戦略や本番発注は変更なし。

## MT5読み取りアダプター

lsr04_mt5_order_draft.read_draftは、渡されたMT5アダプターからaccount_info、
symbol_info、symbol_info_tick、order_calc_profitだけを呼ぶ。order_sendは呼ばない。
既存USDリスク計算との単位混同を避け、USD建てのデモ口座に限定する。
実口座・古い価格・SL損失額未取得・リスク判定時と異なるequityを拒否。
SLは既存構造計算と同じ価格を使用し、BUY Ask/SELL Bidから1lotのSL損失額を見積る。
既にBid/Askで構造SLを突破している案も拒否。
読取前後の口座・equity・仕様・quoteが一致した場合だけ固定注文案へ渡す。
口座識別はローカル乱数付きhashで平文を返さない。nonceもローカル保存専用。

損失額は手数料・滑りを含む保証損失ではない。呼出元が実MT5か模擬adapterかを
暗号学的には認証しない。デモ確認はbroker trade_modeの読取検査である。
最小SL距離・証拠金・取引時間・fill policy・注文送信は後工程。
実Windows口座での本アダプター実行、Dots連携、実約定と収益性は未検証。

## 読取専用デモ事前検査

lsr04_demo_preflight.reviewは上記注文案に、口座・端末の取引許可、銘柄の新規売買方向、
成行・SL・TP対応、価格刻み、SL/TP距離、order_calc_marginによる証拠金見積りを追加する。
情報不足・許可なし・証拠金不足・検査中の口座equity/余剰証拠金/仕様/価格変更は拒否する。
構造SLやTPを動かす、丸める、端末設定を変更する処理はない。

距離は決済側価格（BUYはBid、SELLはAsk）から測り、stopsとfreezeの大きい方を
保守的な注文案用バッファにする。新規注文と既存注文変更のfreeze規則が同一という意味ではない。
証拠金見積り＋指定costが余剰証拠金以内かを確認するが、order_calc_marginは既存ポジション・
未決注文を考慮しないため、実際の注文受理や必要証拠金を保証しない。
内部注文案のbroker_stops_and_margin_checked=Falseは維持し、外側で個別の検査フラグを返す。

取引時間、fill policy、order_check、重複発注防止、約定照合は未実装。
execution_allowed=False、broker_session_verified=False。模擬adapterの単体検査のみで、
このチャットから実Windows/MT5/Dotsには接続していない。

公式仕様：
- https://www.mql5.com/en/docs/python_metatrader5/mt5ordercalcmargin_py
- https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants

## デモ事前照会（注文送信なし）

lsr04_demo_order_check.inspect_orderは、上記事前検査を通した注文案だけをorder_checkへ渡す。
新規成行・固定構造SL/TP・deviation=0・FOK（全量約定または取消）のみに限定。
Request/InstantではFOKを使用し、Market/Exchangeでは銘柄のFOK対応フラグが必須。
IOCやRETURNへの自動切替はしない。Market Executionではrequest.priceを省略するが、
SLリスク計算には現時点のAsk/Bidを使い、実約定価格の保証とは扱わない。

照会は1回のみ。None、非ゼロretcode（order_sendの成功コードも含む）、要求のecho不一致、
不足/非有限の財務結果、見積り後の余剰証拠金不足を拒否する。
照会後に同じnonceで事前検査を再実行し、口座・equity・余剰証拠金・価格・仕様・
執行/fill設定の変更を拒否。実時間を再取得し、quoteから5秒を超えた結果や時計逆行も拒否する。
全読取が原子的である保証はないため、結果を後日の発注承認として再利用しない。

成功statusはDEMO_ORDER_CHECKED_NOT_ORDER_AUTHORIZATION。
execution_allowed=False、duplicate_order_protection_verified=False。
order_send・接続初期化・設定変更・自動再試行は実装しない。
order_check成功は実約定・取引時間・収益性を保証しない。実端末での検証は未実施。
重複発注防止、承認の固定、発注/約定照合は後工程。

公式参照：
- https://www.mql5.com/en/docs/python_metatrader5/mt5ordercheck_py
- https://www.mql5.com/en/docs/constants/structures/mqltraderequest
- https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants

## 永続候補予約（オフライン・発注権限なし）

lsr04_demo_claimsはローカルSQLiteで候補IDを一意に予約する。initializeは明示的新規作成のみ。
同じ口座tokenの同じ候補IDは、quoteや注文案hashが変わっても再予約できない。
BEGIN IMMEDIATEと主キーで並行呼出を直列化し、接続を閉じた後も予約を保持する。
受領済み事前照会の外部SHA・デモ状態・期限を検査し、期限切れでも既存予約を自動解除しない。
DB欠落・破損・口座不一致は停止し、自動再作成しない。データは削除しない。

呼出側は口座nonce/tokenと候補IDを安定保存し、全注文経路で同じDBを使う必要がある。
違う候補ID・別DB・別マシン・別の発注経路を横断する防止や、ブローカー側の冪等性は未検証。
SQLiteの記録と将来のbroker送信は単一トランザクションにできないため、応答不明時に再発注せず、
約定照合する設計が別途必要。本モジュールは実発注経路へ未接続で、実取引の二重発注防止完成とは扱わない。
保存hashは真正性証明ではない。execution_allowed=False、broker_order_sent=False。

## 再起動後も同じ口座として照合する

lsr04_demo_account_context.create_contextは、既に初期化された模擬/MT5 adapterから
DEMO口座の識別を読み、1回だけローカル識別contextを新規保存する。ログイン処理は行わない。
保存内容はschema、DEMO区分、乱数nonce、口座token、execution_allowed=Falseのみ。
口座番号・サーバー名・パスワードは保存しない。nonceは認証情報ではなく、暗号化保管でもない。
context_sha256は別の場所に保持し、紛失時に新規contextや新規予約DBを自動生成しない。

inspect_boundは保存contextをSHAと現在のDEMO口座に照合し、同じnonceでorder_checkを実行。
照会後にもcontextファイル・口座・期限を再確認し、欠落・書換え・別口座・実口座を拒否する。
報告書からnonceを取り除く。新しいadapterインスタンスでも同じ口座tokenを維持する。
check_and_claimは、その結果を既存SQLite予約DBへ渡す。候補IDは上流で確定した同じIDを使う。
再起動やquote変更ごとに候補ID/口座context/予約DBを作り直してはならない。

推奨ローカル名はdemo_account_context.local.jsonとdemo_claims.local.sqlite。
これらとSQLite付随ファイルはGit管理対象外にする。ほかの名前で保存した場合の除外は呼出側の責任。
この連携もorder_sendを実装せず、実デモ口座での発注防止機能の稼働を証明するものではない。
実端末接続・承認固定・約定照合・応答不明時の復旧は後工程。
