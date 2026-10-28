# Windows MT5 DEMO historical pilot

This entry point connects the existing read-only intake, closed-bar structure
adapter, adaptive tick capture, archive/catalog, global quality audit and
matched LSR02/03 price-R study. It is not an EA or a trading terminal control.
No login credentials are accepted, recorded or transmitted, and no order API
is called. It attaches to an explicitly selected, already logged-in terminal.
The broker must report DEMO mode. Live/contest accounts are rejected before
history is read. Keep real trading separate from this research environment.

## Running on the Windows PC with MT5

Use a Python environment where the official MetaTrader5 package is already
available, the repository's fix/fx-safety-verification branch, and the actual
broker terminal executable. A terminal path below is only an example; it is
not automatically selected or assumed correct.

1. Open the broker's MT5 terminal and select the intended DEMO account.
2. Copy pilot_settings.example.json to pilot_settings.local.json.
3. Set the exact source label, historical UTC bounds, research parameters and
   documented cost/slippage assumptions. Do not put account IDs/passwords in
   labels or settings. The source label is not broker authentication.
4. Replace BOTH null cost/slippage values deliberately. Missing/null values
   stop before reading data. Explicit zero remains only an assumption and
   does not certify zero costs. Values are quote-price units per underlying
   unit, not account dollars, commission per lot, or an automatically computed
   broker fee. Calibration is required before a real-cost conclusion.
5. Run with a new output directory:

```powershell
python lsr03_mt5_pilot.py --config pilot_settings.local.json --output orrery_pilot_001 --terminal-path "C:\Program Files\MetaTrader 5\terminal64.exe"
```

The example dates/settings are a schema example, not a recommended profitable
configuration or proof that this broker has continuous history on those dates.
The tick horizon is deliberately <=24h with <=500000 ticks, not a six-month
capture. H4 warmup and lower-timeframe structure starts are separate so a
short tick session can use older context. Warmup must be <=14 days. Start with
one suitable continuous session and inspect data quality before expanding.
One zero-trade report is a valid result, never replaced by invented signals.

## Data and consistency checks

UTC is explicit. MT5 rate timestamps are opening times; this adapter adds
300/900/14400 seconds to obtain close_time and excludes rows closing after
end_utc. It does not reinterpret server offsets or guess a chart timezone.
Required h4/15m/5m streams must be bounded, positive, ordered, continuous and
fresh at the requested historical end. Beginning truncation is detected.
At least one complete 5m->15m and 15m->4H overlap must agree. The existing
lsr02_mt5_bridge aggregation checker is reused, with its previous behavior
preserved. No missing candles or session breaks are interpolated. Weekends,
market closures or insufficient terminal chart history may require a
continuous segment and explicitly chosen context range; this step does not
solve multi-session structural replay.

The bridge checks DEMO/account identity and exact symbol point/contract/digits
before/after each bar fetch, each outer tick chunk and before final completion.
It does not infer symbol suffixes; unsupported canonical names stop. These
checks are not an atomic broker snapshot or source-authentication proof.
The account's raw login/server is not written to output artifacts. User
source labels remain caller assertions and must not contain private data.

Ticks reuse capture_adaptive within each 60-3600 second outer chunk, then the
catalog stores them sequentially. Recursive splits now stay on exact integer
millisecond boundaries and retain half-open coverage, avoiding fractional-ms
manifests. Original submillisecond input bounds are rejected. Saturation,
missing data or resource limits stop; no partial prefix is declared complete.
No session calendar is invented. Long unknown silence blocks the global study.

## Output and interpretation

A new output directory contains ticks/ (pinned catalog and chunk archives),
bars.json, settings.json, report.json, and run.json written last. run.json
binds the catalog pin and hashes of settings, closed bars and report. Retain
run_sha256 and the catalog hash independently. A run-bundle verifier/resume
UI is not added here; existing catalog verification remains available.

- Exit 0: a research comparison report was produced, possibly with zero trades.
- Exit 2: acquisition produced a report blocked by global tick quality.
- Exit 1: configuration/terminal/acquisition/study failed; no completed run is
  promised. Errors are sanitized and raw broker exception details are omitted.

Failed directories are left for inspection and never overwritten or resumed.
Choose a new destination after resolving the problem. Pins detect local
changes relative to retained references, not broker authenticity. No raw
MT5 flags/volume event archive is created. Terminal initialize/shutdown are
owned by main; injected run_pilot callers own their terminal lifecycle.

report.json keeps bar_provenance_verified=False even though the same terminal
and cross-timeframe consistency were checked: OHLC is not reconstructed from
the archived ticks, and warmup predates the pilot tick interval. Costs remain
explicit PRICE-UNIT assumptions. No account-currency net PnL, portfolio DD,
funding-provider rule compliance, official 2.6 definition, OOS edge or live
execution is certified. All outputs keep execution_allowed=False and
market_edge_verified=False. This runner does not activate the account gates
or submit demo orders; it is an offline historical candidate study.

## Validation boundary

Injected fake-DEMO tests cover the full capture->archive->audit->study path,
zero-candidate reporting, unfinished bars, non-DEMO rejection, account/spec
changes, missing/nonfinite costs, future horizons, missing/mixed bars,
failed ticks, exclusive outputs, row limits, identifier omission and read-only
MT5 calls. Adaptive splitting has an odd-duration millisecond-partition test.
Actual Windows terminal connection, Funded7 history availability, realistic
cost conversion and the first actual-market report remain unverified until
this command is run against the intended demo terminal.

Official API reference:
https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesrange_py
