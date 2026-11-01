# Same-candidate fixed vs structural SL research

`python orrery_xau_structural_stop_comparison.py` reuses the public M1/M15
conversion, existing sweep/VHF sequence candidates, and existing hypothetical
fill simulator. The public-data CI runs it and archives the report and exact
candidate window. Source M1/M15/candidate hashes and trade-level prices are
recorded. Existing LSR, VHF, Reversal04 and 2.6 definitions are preserved.

Entry window is 2026-04-25 to 2026-09-25 UTC, half-open. Fixed baseline stop
price distance 6 is compared with the original confirmed M15 sweep candle's
extreme: BUY low, SELL high plus assumed Ask spread. Zero price padding is
an explicit research hypothesis, not a broker-calibrated final SL rule.
The stop is known at sweep close, strictly before confirmation and retest.
Every post-sweep M1 minute before entry must be observed. A prior break/touch
of the anchor invalidates that candidate for this policy; missing pre-entry
history is UNKNOWN, never guessed. Unfinished future candles cannot move
this anchor or retroactively invalidate an earlier entry decision.

Both policies use the same next-M1-open entry, assumed 0.6 price-unit spread,
1.5R TP and 120-minute horizon. TP price differs with SL distance; this is
same RR policy, not the same absolute TP. This fixed-R benchmark does not
replace the independent 2.6 analysis. The simulator now accepts explicit
as-of structural stop specs; its default fixed policy is preserved. R is
normalized by each actual modeled entry-to-stop distance, including timeout
exits. A stop gap uses the observed adverse opening quote rather than
clamping loss at -1R, for BOTH policies. Missing subsequent M1 without an
observed exit stays unresolved. This observed-open handling is not tick-level
slippage or a guarantee of stop execution.

Report all 10 candidates, policy skips and unresolved outcomes separately.
Also show the common resolved subset (7), explicitly subject to selection
bias. Initial local results: fixed all 10 has mean +0.25R; fixed common 7
has 3 wins, mean +0.0714R, PF 1.125. Sweep-extreme policy resolves 7 with
2 wins, mean -0.4224R, PF 0.4086; 3 candidates were invalidated before entry.
This does NOT demonstrate improvement or authorize this stop hypothesis.
It also does not establish that all structural SL designs are ineffective.

These are small, already-inspected public mid-quote research outcomes,
not an executable $3000 account curve. Broker volume/minimum-stop rules,
fees, swap, slippage, margin, floating DD and account loss stops remain
unmodeled in this comparison. No automatic adoption or high-lot permission;
execution_allowed=False and adopted=False. Next diagnose entry freshness
and exit/horizon effects with recorded causal prices before changing rules;
retain baseline losses and report any revised hypothesis separately.
