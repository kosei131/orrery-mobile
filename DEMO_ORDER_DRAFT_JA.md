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
