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
