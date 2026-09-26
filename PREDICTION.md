---
feature: "POST /dora/metrics - DORA five-metric computation and endpoint"
predicted_minutes: 45
predicted_at: "2026-09-26T17:49:55Z"
feature_path: src/svcdesk/metrics.py
---

# Prediction: the `POST /dora/metrics` feature

I predict that building the `POST /dora/metrics` feature will take **45 minutes** of
focused work, measured from the first commit that touches `src/svcdesk/metrics.py`
until the commit that makes the endpoint return the published practice values.

Scope of the prediction: the metric module itself - parsing and validating the JSONL
event log, applying the half-open window, resolving change identity through transitive
reverts, and computing the five metrics plus the counts, anomalies and ground truth -
together with wiring the endpoint into the service. It does not include the receipt
itself, the reasoning artifact or the gaming demonstration.

I am predicting before writing the feature. The measurement is wall-clock minutes
between the first and last commit that touch `feature_path`, and the outcome will be
recorded in `METR.md` as the ratio `actual / predicted` to two decimals. The exercise is
direction-neutral: a speedup and a slowdown are scored identically, so the honest number
matters more than the flattering one.
