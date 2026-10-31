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
