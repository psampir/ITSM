---
lab3_first_draft:
  source: ai
  tool: "OpenCode assistant, model deepseek-v4.1-flash, 24 October 2026, asked in this repository before any measurement"
  ladder: [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1, 2.5]
  verdict: refuted
  evidence: {p99_seconds: 0.1166, bucket: [0.1, 0.25], relative_width: 1.286}
lab3_flawed_ladder:
  verdict: refuted
  evidence: {p99_seconds: 0.1166, bucket: [0.04, 0.5], relative_width: 3.945}
---
<!-- ai-generated: 70% - the assistant wrote the ladder and the alert rule quoted under ## Answer; the prompt, the comparison with my measurement and the verdicts are mine -->

# The assistant's first draft, and two verdicts

## Prompt

Projektuję monitoring dla endpointu `GET /kb/search` w serwisie FastAPI. Endpoint przy każdym żądaniu woła zależność
`kb-index`: jej mediana to około 27 ms, p95 około 47 ms, ale ogon jest ciężki i p99 sięga około 220 ms. Potrzebuję
dwóch rzeczy: (1) granic kubełków histogramu `http_server_request_duration_seconds` w sekundach, (2) gotowej reguły
alertu Prometheus dla SLO dostępności 99% na tym endpointcie. Odpowiedz zwięźle i podaj gotowe listy liczb oraz YAML.

## Answer

### Bucket boundaries

Use the standard ladder. It covers the range an HTTP dependency can produce and
does not need tuning before you have data:

```python
buckets = [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1, 2.5]
```

That is `prometheus_client`'s `DEFAULT_BUCKETS`, so you can also create the
histogram without an explicit `buckets=` argument. The steps are densest below
100 ms, where most requests live, and 250 ms, 500 ms and 1 s catch the tail.

### Alert rule

A 99% availability SLO over a 30-day window leaves a 1% error budget. Alert when
the error ratio over one hour is fourteen times the budget:

```yaml
- alert: KbSearchAvailabilityBurnFast
  expr: |
    sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search", http_response_status_code=~"5.."}[1h]))
      /
    sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search"}[1h]))
      > 14.4 * (1 - 0.99)
  for: 5m
  labels:
    severity: P1
  annotations:
    summary: "GET /kb/search is burning its 99% availability budget 14.4x too fast"
```

Fourteen times the budget over one hour is the classic fast-burn page: at that
rate the 30-day budget is gone in about two days, so somebody should be woken.
For the latency SLO add a second rule on
`http_server_request_duration_seconds_bucket` with the same shape.

## Verdict on the draft ladder

The measurement (`./itsmlab.sh load 3`, 24 October 2026, login `psampir`) gave a p99 of **0.1166 s**: p50 18.4 ms,
p95 31.8 ms, p99 116.6 ms, p99.9 128.8 ms. The draft ladder's boundary 0.1 sits below it and the next one, 0.25,
above it, so the bucket that holds the p99 is **(0.1, 0.25]**.

Its width is 0.25 - 0.1 = 0.15 s, which is 0.15 / 0.1166 = **128.6 % of the p99** - more than six times the 20 %
that M-11 allows. From that bucket `histogram_quantile(0.99)` can report any value between 0.1 and 0.25 s depending
on how the requests happen to be spread inside it, and nothing in the metric warns that the answer is a guess. It is
not a hypothetical: with exactly this draft ladder my first run reported a histogram p99 of 193.8 ms against a true
116.0 ms, 67 % high. The draft is therefore **refuted** - it does not resolve my p99, and the assistant's claim that
the standard ladder "does not need tuning before you have data" is the mistake the laboratory predicts.

## The draft alert rule

The draft is one rule, one window, on the availability SLI: a one-hour error ratio above 14.4 x (1 - 0.99), for 5m.
The idea is right and I kept it: a burn rate multiplier written as arithmetic of two constants, so the threshold is
visible in the expression, and a `for` long enough to survive a scrape hiccup. What I changed:

- I kept the one-hour window but added a **five-minute short window** with `and`. A long window alone keeps firing
  for about half an hour after the burn stops, so the alert cannot reset; the pair is what makes the "reset" probe
  pass and what tells a human the incident is over.
- I added a **second, slower** availability alert (burn rate 6, 6h/30m) because 14.4 pages for a fast burn while a
  slow leak can exhaust the same budget over a day without ever crossing it.
- I added a **latency** alert on the same bucket the SLI counts, because the availability burn rate cannot see the
  slow mode: the 116 ms answers are all 200s.
- I made the labels explicit (`service: svcdesk`, `slo`, `severity`) and left the expression filtered on
  `http_route="/kb/search"`, which the draft had right.

## Verdict on the instructor's flawed ladder

The same p99, 0.1166 s, falls in the flawed ladder's **(0.04, 0.5]** bucket, because twelve of its fourteen
boundaries are spent below 40 ms and then it jumps straight to 0.5. That bucket is 0.46 s wide: 0.46 / 0.1166 =
**394.5 % of the p99**, nearly four times the p99 itself and twenty times the width M-11 allows. The resolution is
spent where the median lives - the 18 ms p50 gets four boundaries between 10 and 40 ms - and the slow mode between
100 and 134 ms, which is the only part of the distribution that matters for a p99 SLO, gets one bucket that spans an
order of magnitude. `histogram_quantile` could report 0.04 s or 0.5 s from it and be "correct" either way. The
verdict is **refuted**, and it is refuted for every profile of this laboratory, not just mine: the bucket is 0.46 s
wide, so it would need a p99 of at least 2.3 s to pass.
