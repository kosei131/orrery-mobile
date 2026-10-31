# As-of public XAU H4 regime attribution

Run `python orrery_xau_h4_alignment.py` after the existing source conversion,
weekly session crosscheck, sequence report, and M15 direct/retest candidate
scripts. CI executes these dependencies and archives `public_xau_h4_alignment.json`.
Normalized M1 and experimental H4 hashes must match the session crosscheck.
The report also records candidate-file hashes and per-candidate annotations.

Reuse `lsr02_regime.classify`, with fixed research parameters: 12 consecutive
H4 bars, trend efficiency 0.3, range efficiency 0.2, confirmed pivots left/right
2. This is an uncalibrated diagnostic, not a trader's validated regime rule.
At each confirmed entry-candidate time, include only H4 close <= that time,
stop at any missing 4h interval, and retain the classifier's stale-data,
insufficient-history and insufficient-confirmed-swings UNKNOWN reasons.
Append-only future candles and outcome values cannot change past annotations.
The weekly calendar remains a publisher hypothesis without historical holiday
certification. ALIGNED/OPPOSED are directional annotations, NOT complete
Type A/Type B strategy classifications or trading authorization.

Compare the three already existing hypotheses over entries in
2026-04-25 through 2026-09-25 UTC, half-open, with unchanged modeled stop
price distance 6, spread 0.6, target 1.5R, 120-minute horizon. These fixed
research exits do not replace structural SL or the independent 2.6 work.
Report candidates and unresolved/unmodeled outcomes separately, including
UNKNOWN. Summaries include resolved-outcome win rate, mean/total R and PF;
empty outcomes and loss-free PF stay null. This does not replay account
loss stops, floating DD, fees, slippage, margin or Funded7 execution.

Initial local result on the 179662-row public source: LSR/VHF 10 candidates,
all UNKNOWN; M15 direct 431 candidates (414 resolved, 17 unresolved), none
ALIGNED; M15 retest 262 candidates (253 resolved, 9 unresolved), none ALIGNED.
The original resolved ALL means remain +0.25R/-0.1629R/-0.2065R. No improved
profit or win rate was demonstrated. The result exposes low classification
coverage; do not loosen thresholds after observing these PnLs or treat zero
ALIGNED as zero-return proof of an effective strategy. Next investigate
UNKNOWN reasons and adequate historical H4 continuity before preregistering
any revised classifier and testing genuinely untouched data.

## Structure-history diagnostic (2026-10-28)

The default `lsr02_regime.classify` behavior remains WINDOW. An explicit
`structure_scope="CONTIGUOUS_HISTORY"` research option uses confirmed pivots
from the supplied complete contiguous prefix while keeping efficiency,
ATR and band on the original last `lookback` bars. Validation still rejects
future/unfinished, unordered and missing bars. Existing replay configuration
and production paths are unchanged. This is a research alternative, not an
assertion that the old specification was a bug.

`annotate(..., full_structure_history=True)` supplies only the contiguous
prefix available at the candidate time. The same report now includes both
modes and reason transitions, with the alternative explicitly `adopted=False`.
No thresholds, entries, stop/TP model, cost assumptions or outcomes are
selected or changed based on this comparison. Both modes use inspected data,
so neither result is out-of-sample evidence.

Observed local diagnostic: LSR/VHF remains 10 UNKNOWN (7 insufficient history,
2 insufficient swings, 1 conflicting evidence). For M15 direct, insufficient
swings falls from 188 to 74 but its 18 ALIGNED resolved outcomes average
-0.3488R (5 wins, PF 0.5171). M15 retest has 10 ALIGNED resolved outcomes,
4 wins, mean +0.008R, PF 1.0138, before unmodeled fees/slippage. This is too
small and too close to zero to demonstrate a profitable implementation.
The previous baseline summaries remain unchanged. Do not adopt the
alternative simply because more candidates receive a directional label.

Priority after this diagnostic: assess the fixed 6-price-unit stop model
against causal structural invalidation with identical cost assumptions,
retaining baseline and unknown outcomes. Additional uninterrupted broker H4
history/session evidence is still required; never bridge unknown closures
just to increase classification coverage. Weekly profit targets do not alter
risk limits or authorize high-lot mode.
