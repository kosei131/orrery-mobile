# Normalized OHLC CSV research input

`lsr02_csv.load_csv` reads a local UTF-8 CSV without modifying it, uploading it or logging its contents. This is NOT a native MT5 export parser or a live feed. MT5 broker timestamps normally require an explicit conversion; no timezone offset, bar-open/close conversion, symbol suffix or missing bar is guessed here.

Exact header and example synthetic row:

```csv
symbol,timeframe,source_id,close_time_utc,open,high,low,close
XAUUSD,5m,SYNTHETIC_FIXTURE,2026-01-01T04:00:00Z,100,101,99,100
```

Use separate files for 4H, 15m and 5m. XAUUSD/USDJPY only; source_id must be identical across the three streams. UTC times must be explicit ISO seconds with Z, aligned to UTC interval boundaries, strictly ordered and continuous. Reject unfinished bars later than caller-supplied as_of. Segment weekend/session gaps before import; do not fill gaps with made-up prices. Maximum 1 MiB and 1000 rows per file limits this to small research segments. UTC-grid alignment is intentionally restrictive and may reject valid broker-specific 4H bars until an explicit mapping is implemented.

`replay_csv(paths, symbol=..., as_of=..., buffer=..., regime_config=..., halt_store=...)` connects normalized files to the offline replay. It returns USER_PROVIDED_UNVERIFIED, input SHA-256 hashes, execution_allowed=False and trace. Matching source IDs or hashes do not authenticate market origin or cross-timeframe OHLC consistency. Neither source labels nor prices are proof of real market data. No live readiness, market profitability, costs or full backtest performance is certified.

Files should contain OHLC only, never login IDs, passwords, account snapshots or private notes. Keep actual datasets outside the repository. Price import is a Python API only: no web file upload, MT5 export utility or user-facing CLI yet. Synthetic tests prove parsing/rejection and routing only; real broker export conversion and evaluation remain unverified.
