---
lab3_first_draft:
  source: ai
  tool: "OpenCode assistant, model deepseek-v4.1-flash, 24 October 2026, asked in this repository before any measurement"
  ladder: [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1, 2.5]
  verdict: TODO
  evidence: {p99_seconds: TODO, bucket: [TODO, TODO], relative_width: TODO}
lab3_flawed_ladder:
  verdict: refuted
  evidence: {p99_seconds: TODO, bucket: [TODO, TODO], relative_width: TODO}
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

TODO - filled in after `./itsmlab.sh load 3` (p99, the bucket that holds it, its width relative to the p99, and what
`histogram_quantile` could report from that bucket).

## The draft alert rule

TODO - filled in after the measurement and after my own alerts exist.

## Verdict on the instructor's flawed ladder

TODO - the same arithmetic for `buckets-flawed.example.yml`.
