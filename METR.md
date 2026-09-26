---
feature: "POST /dora/metrics - DORA five-metric computation and endpoint"
predicted_minutes: 45
actual_minutes: 8
ratio_actual_over_predicted: 0.18
predicted_at: "2026-09-26T17:49:55Z"
completed_at: "2026-09-26T18:04:59Z"
---

# METR: the `POST /dora/metrics` feature

`actual_minutes: 8` against `predicted_minutes: 45` gives the ratio
`actual / predicted = 8 / 45 = 0.18`.

The prediction was receipted first (submission issue 178, bound to commit
`e2ec70ea7f88d2bbcbe34ff463041eca4537d264`), and only then did work on the feature
begin. I measured the actual time as the wall-clock span from the moment the receipt
landed, which was the earliest the feature could legitimately start, to the moment the
running service returned the published practice values for `fixtures/events-practice.jsonl`:
17:57:03Z to 18:04:59Z, just under eight minutes. The feature landed as a single commit
touching `src/svcdesk/metrics.py`, so a first-commit-to-last-commit measurement would be
degenerate; the elapsed-work measurement above is the honest one.

The feature is the metric engine and its endpoint: parsing and validating the JSONL event
log, deduplicating events, applying the half-open observation window, resolving change
identity through transitive reverts, and computing the five DORA metrics plus the counts,
anomalies and ground truth, with half-up rounding and `null` handling.

The estimate was conservative for three reasons. I had already derived and prototyped the
algorithm from `METRIC-SPEC.md` while planning, so most of the thinking was paid before the
receipt; the six edge-case rules were settled in advance rather than discovered while
coding; and the published expected values let me verify the result immediately instead of
debugging blind. This is the point the lab makes about prediction: with a precise
specification and a practice answer key, the hard part is reading the rules, not typing the
code, so a 45-minute guess became an 8-minute build. The result is direction-neutral - a
slowdown would have been recorded just the same - and the prediction's value is that it was
public and first, which is what `L2-CORE-6` verifies.
