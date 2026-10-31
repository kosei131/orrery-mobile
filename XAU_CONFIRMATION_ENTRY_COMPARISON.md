# All-confirmation entry vs retest waiting

`python orrery_xau_confirmation_entry_comparison.py` runs after the existing
public-bar conversion and `orrery_public_xau_sequence_study.py`. CI archives
its report and both exact entry-plan files.

The sequence report now retains `confirmation_evidence` for every causally
matched VHF-passed M15 sweep/M5 confirmation, before examining later POI
retouches. The existing 14 full-sample retouches and all previous report
fields were checked against the previous implementation and are unchanged.
A separate retest observer walks subsequent M5 closes, requiring no missing
bar before a touch. A touch before a later gap survives. Complete no-touch
60-minute windows expire; incomplete windows are UNKNOWN, not expiry or a
future fill. Missing POI is explicit. None of these future statuses select
confirmation-entry candidates.

The shared cohort is confirmations in [2026-04-25,2026-09-25) UTC. Both
entry rules also require entry inside that window. Confirmation entry uses
the modeled next M1 open at confirmation close; waiting uses the first
later confirmed M5 POI touch close within 60 minutes. Both are hypothetical,
not guaranteed executable prices. The legacy simulator input field
`first_poi_touch_close` denotes entry time in the immediate plan file; its
explicit `entry_rule=CONFIRMATION` does NOT claim that a POI touch occurred.
Each plan records its sweep/confirmation/side identity.

Two fixed, existing stop hypotheses are tested independently: fixed price
distance 6 and sweep extreme. Existing structural-stop builder now permits
entry exactly at confirmation close, preserving pre-entry M1 checks and
sweep-known stop timestamps. No current-entry/future M1 is used to approve
pre-entry structural validity. Same assumed spread 0.6, TP 1.5R, exit
horizon 120 minutes and exit engine for all four arms. No thresholds,
VHF parameters, line definitions, risk limits or 2.6 definitions changed.

Initial local results: 30 full-sample confirmations, 22 in the study cohort.

| Entry / SL | Planned entries | Resolved | Wins | Mean R | PF |
| --- | ---: | ---: | ---: | ---: | ---: |
| Confirmation / fixed 6 | 22 | 21 | 10 | +0.1905 | 1.3636 |
| Confirmation / sweep extreme | 22 | 13 | 8 | +0.1307 | 1.3611 |
| Retest / fixed 6 | 10 | 10 | 5 | +0.2500 | 1.5000 |
| Retest / sweep extreme | 10 | 7 | 2 | -0.4224 | 0.4086 |

Waiting has 11 expiries and 1 unknown-history window among 22 confirmations.
Confirmation/fixed has 1 unresolved post-entry outcome. Confirmation/structure
has 8 pre-entry structural invalidations and 1 unresolved outcome; waiting/
structure has 3 pre-entry invalidations. These are retained as explicit
policy skips/unknowns, not wins, losses or zero-return trades. Mean R is
conditional on resolved outcomes, and different arm means alone cannot
identify the better executable strategy or account profit.

On the 10 common fixed-stop resolved confirmations, immediate entry averages
-0.5R versus retest +0.25R. This is supplementary hindsight attribution,
NOT permission to select immediate entries by future retouch survival.
The report separately attributes immediate outcomes by eventual retest
status under `future_retest_attribution_NOT_AN_ENTRY_FILTER`; this must never
be turned into an as-of filter. Waiting can avoid losses and miss profits.

All observations are small and already inspected. No H4 filter, real broker
Bid/Ask/fees/slippage, margin, portfolio overlap execution or account loss
stops are modeled here. No 95% win-rate, Kou replication, formal Type A/B
classification, complete $3000 six-month result or trading authorization.
`adopted=False`, `execution_allowed=False`. Next evaluate candidate lifecycle
and these entry alternatives through the existing account replay on verified
quotes and costs; preserve unresolved records and the untouched-data boundary
before testing partial exits or position additions.
