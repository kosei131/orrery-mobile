# ORRERY FX — Windows MT5 local auto-refresh dashboard (v7)

This stage runs **only on your Windows PC**. It does not connect the iPhone app to MT5 and does not send market/account data to GitHub, Cloudflare or other servers.

## Run
1. Start Windows MetaTrader 5 and sign in to **MetaQuotes-Demo**.
2. Install Python for Windows if needed.
3. In PowerShell run `py -m pip install MetaTrader5`.
4. Download `mt5_local_dashboard.py` from this repository.
5. Open PowerShell in the download directory and run `py mt5_local_dashboard.py`.
6. It prints a private local address starting `http://127.0.0.1:8765/#...`. **On that same PC**, open the full URL in the browser.
7. Balance, equity, free margin, positions, and seven-day deal count request updates every second (an in-flight request is never overlapped; slow MT5 responses and background browser throttling can reduce the actual update rate). Stop with Ctrl+C.

## Safety
- Uses only MT5 `initialize`, `account_info`, `positions_get`, `history_deals_get`, and `shutdown` API calls; **no trading/order API calls**.
- Refuses REAL accounts. Does not ask for, store or upload MT5 passwords.
- HTTP server listens on loopback `127.0.0.1` only, not external network.
- Generates a temporary token at each startup; do not share the printed URL.
- Works only while this process and the Windows MT5 terminal are running.
- This is a development diagnostic. It does not implement Face ID, encrypted cross-device synchronization, funded account execution, or live trading.

## Troubleshooting
- If port 8765 is in use, quit any other running instance before restarting.
- If the terminal reports no connection, open Windows MT5, verify DEMO login and repeat.
- Python MT5 package currently requires supported Windows Python and MetaTrader 5 desktop.

## Next stage
A separately authenticated HTTPS transport and access controls are needed before private snapshots can safely appear on an iPhone. Do not expose this localhost service to the Internet using router port-forwarding.

This is account/position snapshot polling, not a market-price candlestick feed. Completed 4H/15m/5m bars retain their own close schedule. Simulated FX candles still advance manually; TradingView data cadence is controlled by its provider.

## DEMO broker quotes (experimental)
The latest local dashboard reads `symbol_info_tick` for exact symbols XAUUSD and USDJPY already available in the terminal. It does not select symbols or guess broker suffixes. Missing or invalid ticks are unavailable; timestamps over 10 seconds old or in the future are rejected. This threshold is a research freshness rule, not a trading permission. Weekends/closed sessions may show unavailable prices. No synthetic fallback. The DEMO account identity is rechecked after account and quote reads; changed accounts cause the whole snapshot to be discarded. This is best-effort switch detection, not an atomic terminal lock.

Quotes are broker-provided DEMO Bid/Ask, not a candlestick chart or guaranteed execution prices. They are separate from the simulated FX page, TradingView and LSR replay. Browser requests occur at one-second intervals; new market ticks depend on the broker. Actual Windows terminal quote delivery and performance remain unverified. No data is persisted or uploaded.

## Closed 5-minute candles
The local DEMO snapshot now includes up to 70 closed 5m bars for exact XAUUSD/USDJPY symbols. Requests start at MT5 bar index 1; index 0 (forming bar) is excluded. OHLC/order/continuity/future-close checks are applied; gaps, unavailable history or a last close more than 300 seconds old suppress rendering. Weekend/session gaps are not interpolated. Browser requests are every second, but closed candles only become available at their own interval boundaries. There is no live forming candle, LSR wiring or trade execution. DEMO account identity is checked after both quote and candle reads. Actual Windows terminal data/performance remains unverified; mocked tests and intercepted synthetic browser responses verify correctness only.

## Multi-timeframe chart selection
The dashboard also requests closed 15m and 4H history, up to 70 bars for each symbol/timeframe. A selector switches the visible chart. Freshness and continuity are checked independently at 300/900/14400-second intervals. If one series is unavailable, no other timeframe is substituted. UTC alignment is required; broker-specific 4H alignment may be rejected until explicitly supported. Quotes still request updates every second; closed candles advance at their own timeframe boundaries. Data retrieval/performance against a real terminal remains unverified. Timeframe selection after a failed request must not restore cached chart data. This display is not yet wired into LSR-02 signal generation.
