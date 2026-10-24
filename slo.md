---
lab3_slo:
  service: svcdesk
  route: /kb/search
  window: 28d
  slis:
    availability:
      objective: 0.99
      good: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search", http_response_status_code!~"5.."}[5m]))'
      valid: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search"}[5m]))'
      error_budget: {fraction: 0.01, minutes: 403}
    latency:
      objective: 0.98
      threshold_seconds: 0.125
      good: 'sum(rate(http_server_request_duration_seconds_bucket{job="svcdesk", http_route="/kb/search", le="0.125"}[5m]))'
      valid: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search"}[5m]))'
      error_budget: {fraction: 0.02, minutes: 806}
  alerts:
    - {alert: KbSearchAvailabilityBurnFast, sli: availability, burn_rate: 14.4, long_window: 1h, short_window: 5m}
    - {alert: KbSearchAvailabilityBurnSlow, sli: availability, burn_rate: 6, long_window: 6h, short_window: 30m}
    - {alert: KbSearchLatencyBurnSlow, sli: latency, burn_rate: 6, long_window: 6h, short_window: 30m}
---
<!-- ai-generated: 70% - the assistant drafted the structure and the front matter; the numbers, the defence and the alert choices are mine, from the measurements of 24 October 2026 -->

# SLO for `GET /kb/search`

## Availability

The availability SLI is the share of `/kb/search` requests that did not answer 5xx: `good` counts every request whose
`http_response_status_code` is not `5..`, `valid` counts all of them. The service answers 200 on success and 502 when
`kb-index` fails, so the only 5xx this route can produce is our own `upstream_unavailable` translation - every one of
them is a request the user did not get an answer to.

The objective is **0.99 over 28 days**, an error budget of 0.01 = **403 minutes** (28 x 1440 = 40,320 minutes).
`kb-index` fails about 0.2 % of its ordinary searches by design, and I cannot fix that: those failures arrive as a 502
from my service and spend my budget. Measured twice on 24 October: 3 and 6 failed requests out of 2,400, 0.13 % and
0.25 %. A 99.9 % objective would therefore be met only in the luckiest of windows, and an objective the service cannot
meet would make Lab 6's canary gate roll back an honest release. 99 % leaves roughly eight tenths of a percentage
point of headroom for the dependency's own error rate, for restarts and for the occasional slow request that times out
at the client - enough that a normal day never burns the budget, tight enough that a real outage (a tenth of requests
failing) exhausts it in about eleven hours.

## Latency

The latency SLI is the share of `/kb/search` requests that completed in **at most 0.125 s**: `good` is the
`http_server_request_duration_seconds_bucket` with `le="0.125"`, `valid` is the histogram's `_count`. 0.125 s is one
of the ladder's finite boundaries, so the SLI counts requests rather than interpolating inside a bucket (M-13).

The distribution I measured (p50 18.4 ms, p95 31.8 ms, p99 116.6 ms, p99.9 128.8 ms) is bimodal: 94 % of the
requests answer in 8-46 ms, then a slow mode starts around 100 ms - the dependency's seeded tail - and carries the
p99 to 116 ms. A threshold below 0.1 s would make the SLI depend on the slow mode's jitter and would fail honest
windows; a threshold at 0.15 s or 0.2 s would sit so far above the p99 that it would only catch a catastrophic
failure. 0.125 s sits just over the measured p99 (1.07 x q) and just under the p99.9 (128.8 ms): it separates "the
slow mode happened to be slow" from "the slow mode got slower", which is exactly what a latency SLO for this
dependency should watch.

The objective is **0.98 over 28 days**, an error budget of 0.02 = **806 minutes**. At 40 requests per second that is
2 % of about 1.6 million monthly requests. The measured share below 0.125 s is above 99.4 %, so 98 % is met with more
than a percentage point of margin - the same argument as above: Lab 6 reads this threshold and this objective as a
canary gate, and an objective that only a perfect run meets would roll back honest releases.

## Alerts

| alert | SLI | burn rate | long / short window | budget spent when it fires | severity: page or chat |
|---|---|---|---|---|---|
| KbSearchAvailabilityBurnFast | availability | 14.4 | 1h / 5m | 14.4 x the sustainable rate: the 28-day budget in about 2 days | P1 - page |
| KbSearchAvailabilityBurnSlow | availability | 6 | 6h / 30m | 6 x: the budget in about 4.7 days | P2 - chat |
| KbSearchLatencyBurnSlow | latency | 6 | 6h / 30m | 6 x of the 2 % latency budget: in about 4.7 days | P3 - chat |

Every alert compares a bad-request ratio against `burn_rate * (1 - objective)` written as constants in its own
expression, and every one of them requires both the long and the short window to be over the threshold, so an
incident that has stopped stops the alert within the short window instead of keeping it firing for half the long one.

The fast availability alert pages (**P1**). At 14.4x the budget is gone in about two days, and the cause is almost
always the dependency: an `upstream_unavailable` storm or a deployment of mine that broke the proxy. Waking somebody
at night costs one person one night; waiting until morning costs the users 14.4 % of their requests for eight hours -
at 40 requests per second, some 165,000 failed searches. That trade is worth the page.

The slow availability and latency alerts go to chat (**P2**, **P3**). At 6x the budget survives four to five days, so
the next working morning is soon enough to look at it; paging would spend a night of a human's sleep to save a budget
that is still 80 % intact. The slow alerts exist because the fast one cannot see a leak: 0.5 % of requests failing
forever never crosses 14.4 %, exhausts the same budget in a month and would otherwise be found by the users.

## Buckets

The ladder has 29 finite boundaries, in seconds:

    0.005 0.01 0.015 0.02 0.025 0.03 0.035 0.04 0.05 0.06 0.07 0.08 0.09 0.095
    0.1 0.105 0.11 0.115 0.12 0.125 0.13 0.135 0.14 0.15 0.16 0.18 0.2 0.3 0.5

The measured p99, 0.1166 s, falls in **(0.115, 0.12]** - 0.005 s wide, **4.3 % of the p99**. The thirteen
boundaries from 0.095 to 0.15 exist to resolve a band of **+/-10 % around q** (0.105 to 0.128 s): every bucket in
that band is 5 ms wide, and 5 ms is at most 4.8 % of the band's lower end, well inside the 20 % M-11 allows. That
band is the whole point: another machine and another 2,400 draws moved q from 116.0 to 116.6 ms in two consecutive
runs, and the grader's q will move again; a ladder with one fine bucket would fail the moment q stepped into its
neighbour.

The rest of the boundaries are spent where a dashboard needs them and nowhere else. The three coarse steps below
0.02 s describe the median mode (18 ms) and the 40 ms shoulder, so a p50 panel is not an interpolation over a
hundred milliseconds. The four above 0.15 s (0.16, 0.18, 0.2, 0.3, 0.5) bound the far tail: the p99.9 sits at
128.8 ms and the p99.99 at 134.1 ms, so anything beyond 0.15 s is already an exception and only needs to be counted,
not measured precisely. That leaves three boundaries of slack under the limit of 30, which I keep for a future
deployment whose slow mode moves.
