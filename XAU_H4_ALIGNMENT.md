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
