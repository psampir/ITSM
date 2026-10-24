---
lab4_postmortem:
  ticket: "50ceffde-fa49-40b3-b4ca-957734d74bf7"
  detecting_alert: ShopCheckoutErrors
  onset: 2026-10-12T06:36:23Z
  detection: 2026-10-12T06:39:19Z
  acknowledgement: 2026-10-12T06:40:09Z
  recovery: 2026-10-12T06:44:19Z
  mttd_seconds: 176
  mtta_seconds: 50
  mttr_seconds: 476
  identified_flags: [paymentFailure, loadGeneratorFloodHomepage, recommendationCacheFailure]
---
<!-- ai-generated: 70% - opencode drafted the text from the queries I ran on the snapshot and from incident 4's output; I checked every number and rewrote the narrative -->

# Postmortem: checkout refused one order in five, and the front page took fifteen times its normal traffic

## Date

The incident happened on Saturday 12 October 2026, between 06:36:23Z and 06:44:19Z. This postmortem was written the
same day, from the Prometheus snapshot of the run and the P1 ticket it left behind.

## Authors

Written by the on-call engineer who worked the incident (the author of the P1 ticket), reviewed by the service owner
of checkout and by the platform team that runs the feature-flag service.

## Status

Complete, action items in progress. The incident record is closed with the service restored; the problem record at
the end of this document stays open until the flags that caused it are removed from the demo.

## Summary

For about seven minutes the shop could not take payments: one checkout in five failed with a 502 while the front page
was hit by roughly fifteen times its normal traffic. The cause was a set of three feature flags switched on by the
fault injector at 06:36:23Z: `paymentFailure` made the payment service refuse charges, `loadGeneratorFloodHomepage`
multiplied the load generator's front-page traffic, and `recommendationCacheFailure` broke the recommendation cache.
The page reached the on-call at 06:39:29Z, the ticket was acknowledged 40 seconds later, and switching the flags off
at 06:43:15Z restored service.

## Impact

Between 06:36:23Z and 06:43:15Z checkout answered 41 `PlaceOrder` requests and **8 of them failed - 19.6 %**. Both
numbers come from the snapshot:
`sum(increase(traces_span_metrics_calls_total{service_name="checkout", span_kind="SPAN_KIND_SERVER", status_code="STATUS_CODE_ERROR"}[7m]))`
returned 8.2 at 06:43:20Z against
`sum(increase(traces_span_metrics_calls_total{service_name="checkout", span_kind="SPAN_KIND_SERVER"}[7m]))`
at 40.9. Every failed order is one refused charge in the payment service (same query with `service_name="payment"`,
8.2 failures), so no customer was charged for an order that did not complete.

The second symptom was load, not failure: the frontend answered **20,613** SERVER requests in the fault window against
**1,501** in the seven minutes before it - 13.7 times the baseline, measured with
`sum(increase(traces_span_metrics_calls_total{service_name="frontend", span_kind="SPAN_KIND_SERVER"}[7m]))` at
06:43:20Z and 06:36:00Z. Latency did not move: the p99 of checkout's SERVER spans stayed at the 49 ms it had on the
healthy shop (`histogram_quantile(0.99, sum by (le) (rate(traces_span_metrics_duration_milliseconds_bucket{service_name="checkout", span_kind="SPAN_KIND_SERVER"}[5m])))`),
so users saw errors, not a slow shop.

## Root Causes

Three faults, one per class of the injector's pool, were active at the same time.

`paymentFailure` is the one that hurt: payment answered a share of `Charge` calls with an error, and checkout, which
has no fallback, turned every one of them into a failed order (`oteldemo.PaymentService/Charge`, 0.0297 failed calls
per second at 06:41). `loadGeneratorFloodHomepage` made the load generator browse the home page about fifteen times
harder, which is why the frontend and the frontend proxy carried 13.7 times their normal request rate without
failing. `recommendationCacheFailure` is the quiet one: the recommendation service's resident memory climbed from
53.8 MB at the onset to 60.2 MB four minutes after it, where the healthy service sits flat at 57-58 MB, and its cache
was rebuilt after the flags went off - memory and cache behaviour are exactly what that flag breaks, and nothing else
in the shop moved.

What was already wrong, before any flag: checkout treats a refused payment as a terminal error instead of a
retryable one, and no alert watched the frontend's request rate, so the flood was invisible until checkout started
failing because of it.

## Trigger

The fault injector was armed and drew its fault at 06:31Z; the three flags switched on together at **06:36:23Z**, the
onset the snapshot records as the first sample of `seeded_fault_active`. Nothing on the shop changed before that
instant: the payment error counter was zero at 06:31:23Z, five minutes before the onset.

## Resolution

The flags were switched off through the injector at **06:43:15Z**, when `seeded_fault_active` fell from 1 to 0.
`paymentFailure` went first, because the failing charge was the only symptom users could see; the flood and the cache
flag followed, since neither of them was producing errors of its own. The detecting alert, `ShopCheckoutErrors`,
resolved at 06:44:19Z when its five-minute window had slid past the last failure, and the pager showed the resolved
notification at 06:44:29Z.

## Detection

`ShopCheckoutErrors` fired at **06:39:19Z**, **176 seconds** after the onset, on the ratio of failed to total
`PlaceOrder` SERVER spans over five minutes crossing 5 % for two minutes. Alertmanager paged the on-call at 06:39:29Z
(the pager's own `itsm_pager_notifications_total{receiver="pager",status="firing"}` counter rises at that instant) and
the ticket was acknowledged at 06:40:09Z, 50 seconds after the detection.

Without the alert nobody would have noticed for several minutes: the shop's Grafana dashboards were not open, the
front page still answered 200, and the only failing signal was a low-traffic error counter on checkout. The alert
earned its page.

## Action Items

| Action Item | Type | Owner | Bug |
|---|---|---|---|
| Retry a refused `Charge` twice with backoff and only fail the order after that | mitigate | checkout team | ITSM-41 |
| Add a P1 on the frontend's SERVER request rate, so a fifteen-fold flood pages on its own symptom and not only through checkout | prevent | on-call lead | ITSM-42 |
| Put a size cap and an eviction policy on the recommendation cache, and alert when its resident memory grows faster than 1 MB/min | prevent | recommendation team | ITSM-43 |
| Attach the checkout runbook and the injector's `/flags.json` link to the `ShopCheckoutErrors` notification | process | on-call lead | ITSM-44 |

## Lessons Learned

### What went well

The page arrived 176 seconds after the onset and the on-call acknowledged it in 50 seconds. The error-ratio alert was
specific enough that nobody chased the load generator's own failing client calls, which fail all the time on the
healthy shop. Within two minutes of the page the failing dependency was named from the metrics alone.

### What went wrong

Checkout has no degradation path for a refused payment: one dependency's error becomes the shop's error. The flood
was invisible to our alerting - it only became a page when checkout failed because of it - and the recommendation
cache moved without any alert watching it. The first hypothesis the AI investigator stated blamed the payment
service's "core transaction processing logic", which is true but too vague to act on by itself.

### Where we got lucky

The fault was short and the payment failure was only 10-25 % of charges: a higher share would have failed every
order, and then the 5 % error-ratio alert would still have paged, but the on-call would have had no successful
payment to compare against. We were also lucky that the recording's frontend proxy did not fall over at 13.7 times
the baseline traffic; it has no rate limit.

## Timeline

All times UTC, from the last quiet minute before the onset to the recovery.

- **06:35:20Z** - the last healthy minute: payment's error counter is flat, the frontend answers about 3.5 requests
  per second.
- **06:36:23Z** - **onset**. The injector switches on `paymentFailure`, `loadGeneratorFloodHomepage` and
  `recommendationCacheFailure`; `seeded_fault_active` first reads 1 at 06:36:25Z.
- **06:36:50Z** - the frontend's memory and request rate start climbing: the flood is under way.
- **06:37:40Z** - the first refusals reach checkout: `oteldemo.PaymentService/Charge` fails.
- **06:39:19Z** - **detection**: `ShopCheckoutErrors` fires; the pager notifies at 06:39:29Z.
- **06:39:44Z** - the P1 ticket is opened in `svcdesk` (impact 1, urgency 1).
- **06:40:09Z** - **acknowledgement**.
- **06:40:20Z** - `ShopServiceErrors` (P2) starts firing on the same symptom; it goes to chat, not the pager.
- **06:43:15Z** - the three flags are switched off; `seeded_fault_active` falls to 0.
- **06:44:19Z** - **recovery**: `ShopCheckoutErrors` resolves when its five-minute window is past the fault.
- **06:44:29Z** - the pager shows the resolved notification.

The AI investigator's three hypotheses entered this timeline only with their queries: H1 and H2
(`sum(rate(traces_span_metrics_calls_total{service_name="payment", span_kind="SPAN_KIND_SERVER", status_code="STATUS_CODE_ERROR"}[5m]))`)
confirmed the payment failure at 06:41, and H4
(`sum(rate(traces_span_metrics_calls_total{service_name="checkout", span_name="oteldemo.PaymentService/Charge", span_kind="SPAN_KIND_CLIENT", status_code="STATUS_CODE_ERROR"}[5m]))`)
confirmed the call path from checkout. H3 was true as well but added nothing the two others had not said.

## Supporting information

- The snapshot `incident/tsdb-snapshot.tar.gz` (run `c1daa7d0f4acf990`) and the ticket
  `incident/ticket.json`; `itsmlab incident 4` recomputes the four instants and the three durations from them.
- The queries of the Impact and Detection sections, run on the snapshot's Prometheus with an explicit time.
- The AI ledger `ai-rca-eval.json` and its transcript `ai-rca/transcript.md`; entries H1 and H4 are the two the
  timeline cites.
- Dashboard: the demo's Grafana, panels `frontend` request rate and `checkout` error ratio.

## Problem record

- Incident record: 50ceffde-fa49-40b3-b4ca-957734d74bf7 - the P1 ticket, closed when the flags were switched off and service returned.
- Root cause: feature flags seeded into the demo's flagd by the course fault injector (`paymentFailure`, `loadGeneratorFloodHomepage`, `recommendationCacheFailure`), each switched on by a single control plane that no service validates.
- Known error: a refused `Charge` propagates to the customer as a failed order because checkout has no retry or degradation, and a fifteen-fold rise in front-page traffic produces no alert of its own.
- Workaround: switch the offending flag off through the injector's `/flags/{key}/off`, which restores the service within the detecting alert's five-minute window without a deployment.
