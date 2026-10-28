# Explicit session-aware research bars

The existing `orrery_m1_complete_bars.aggregate` accepts optional `calendar=`.
Without it the original exact 240/15/5 M1 requirement remains unchanged.
A supplied calendar must name its `source` and contain contiguous, ordered
`intervals`, each with explicit UTC minute-aligned `start_utc`, `end_utc`,
and `state` OPEN or CLOSED. Bounds are half-open; overall horizon must align
to the requested UTC bar grid and cannot exceed 366 days.

Example schema (illustrative only, NOT an XAU trading schedule):

```json
{"source":"independently checked feed schedule reference", "intervals":[
  {"start_utc":"2026-10-22T00:00:00+00:00","end_utc":"2026-10-22T03:00:00+00:00","state":"OPEN"},
  {"start_utc":"2026-10-22T03:00:00+00:00","end_utc":"2026-10-22T04:00:00+00:00","state":"CLOSED"}
]}
```

Every OPEN minute must have exactly one actual M1 candle. Missing open
minutes, including an entirely absent open bucket, cause that bar to be
rejected. Quotes in CLOSED minutes or outside coverage raise an error.
All-closed buckets produce no candle. Complete partial-session bars use
actual observed OHLC only, retaining UTC grid open and close times. No
forward filling or holiday/weekend inference is performed. The existing
bridge still reports gaps between entirely closed grid buckets; this change
does not authorize replay across weekends. Nonfinite OHLC are rejected.

CLI: `python orrery_m1_complete_bars.py source.csv --period H4 --out h4.csv --calendar-json checked_calendar.json`.
Calendar source and canonical SHA256 are reported for reproducibility, but
an input label/hash does not authenticate a broker schedule. Outputs keep
`calendar_broker_verified=False` and `execution_allowed=False`. Historical
session changes/DST/holidays and source-specific candle semantics must be
checked independently. The public XAU pipeline is deliberately unchanged:
no verified source schedule has been provided. This adds capability, not
new performance results or a validated H4 regime filter. Existing LSR,
VHF, Reversal04, 2.6 and account risk settings are unchanged.

Next: obtain the publisher/broker session evidence and native H4 comparison;
then evaluate as-of Type A/Type B separately with structural SL, realistic
costs and untouched data. Weekly +$5000 remains a goal, never an override
of the 0.25% research risk or loss stops.
