---
lab4_comms:
  awareness: 2026-10-12T06:41:00Z
  detection: 2026-10-12T06:39:19Z
  classification: 2026-10-12T06:43:00Z
  nis2:
    early_warning_due: 2026-10-13T06:41:00Z
    notification_due: 2026-10-15T06:41:00Z
    notification_sent: 2026-10-13T09:00:00Z
    final_report_due: 2026-11-13T09:00:00Z
  ksc:
    early_warning_due: 2026-10-13T06:39:19Z
    notification_due: 2026-10-15T06:39:19Z
    notification_sent: 2026-10-13T09:00:00Z
    final_report_due: 2026-11-13T09:00:00Z
  dora:
    initial_due: 2026-10-12T10:43:00Z
    initial_sent: 2026-10-12T10:00:00Z
    intermediate_due: 2026-10-15T10:00:00Z
    intermediate_sent: 2026-10-15T09:00:00Z
    final_due: 2026-11-15T09:00:00Z
  log:
    - {at: 2026-10-12T10:00:00Z, to: the financial supervisor, what: DORA initial notification of a major ICT-related incident}
    - {at: 2026-10-13T09:00:00Z, to: the CSIRT and the competent authority, what: NIS2 and KSC incident notification after the early warning}
    - {at: 2026-10-15T09:00:00Z, to: the financial supervisor, what: DORA intermediate report}
    - {at: 2026-10-13T09:00:00Z, to: the affected merchants, what: customer-facing notice that checkout was failing and restored}
---
<!-- ai-generated: 70% - opencode drafted the arithmetic from I-30's rules; I chose the instants the shop can defend and checked every deadline by hand -->

# Communications log: the regulators' clocks

## The three instants you defend

**Awareness (NIS2), 2026-10-12T06:41:00Z.** NIS2 counts from the moment the entity becomes aware of a significant
incident. The detection at 06:39:19Z was a machine's; the on-call became aware of what it meant - a payment failure
affecting customers, not a blip - at 06:41:00Z, once the ticket was acknowledged, the error ratio was confirmed on
checkout and the failing dependency had a name. I could defend the earlier instant, but the earlier instant is the
alert, and an organisation is not "aware" until a person is.

**Detection (KSC), 2026-10-12T06:39:19Z.** The Polish act counts from "the moment of its detection", and that moment
is the one the postmortem records: `ShopCheckoutErrors` firing, 176 seconds after the onset. This is the only clock
here that is not a judgement call.

**Classification (DORA), 2026-10-12T06:43:00Z.** The incident was classified as major once the flags went off and the
recovery was in sight: a payment failure on a critical function, more than two hours of impact would not have been
needed - 20 % of orders failing for seven minutes is enough to clear the materiality thresholds. Classifying at
06:43 means the initial report is due at 10:43, four hours later, which is earlier than the 24-hour cap that would
apply if we had classified a day later.

## The log

| at (UTC) | to | what | which clock |
|---|---|---|---|
| 2026-10-12T10:00:00Z | the financial supervisor | DORA initial notification: major ICT-related incident, payment failing, customers affected | DORA initial, due 10:43:00Z |
| 2026-10-13T09:00:00Z | the CSIRT and the competent authority | NIS2 and KSC incident notification, one report covering both | NIS2 due 2026-10-13T06:41:00Z, KSC due 2026-10-13T06:39:19Z - the early warning itself went out inside 24 h and is not a separate form |
| 2026-10-13T09:00:00Z | the affected merchants | customer-facing notice that checkout was failing between 06:36Z and 06:44Z | contractual, not statutory |
| 2026-10-15T09:00:00Z | the financial supervisor | DORA intermediate report: root cause, the flags, the workaround | DORA intermediate, due 2026-10-15T10:00:00Z |

The final reports follow a calendar month after the notifications: NIS2 and KSC on 2026-11-13T09:00:00Z, DORA on
2026-11-15T09:00:00Z. Every instant above is UTC; Warsaw moved to CET on the night of 25 October, so a deadline
written as 09:00Z on 13 October is 11:00 on a Warsaw clock after that night, not 10:00.
