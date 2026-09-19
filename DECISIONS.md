---
svcdesk_decisions:
  C1: wallclock
  C2: reopen
  C3: vip
---
<!-- ai-generated: 70% - opencode drafted the wording from the resolutions chosen and reviewed by the student; the reasoning and the final choice are the student's -->

# Decisions

Each section names the conflict, the resolution the running service exhibits, the part of the rejected
requirement, and who bears the consequence.

## C1 - SLA clock for P1

**Decision:** A P1 ticket is measured on the wall-clock for both targets: acknowledgement due 15 minutes and
resolution due 4 hours after creation, with no pause for nights or weekends. Every other priority (P2 to P4)
keeps the business-hours clock of Monday to Friday, 08:00 to 16:00 Europe/Warsaw.

**Rejected alternative:** Putting P1 on the same business-hours clock as every other priority, which is what
R-13 asks for when read on its own; under that reading a P1 raised on Friday at 17:00 would not fall due until
Monday morning.

**Reason:** R-13 and R-14 cannot both hold for P1, so one of them must give way for that priority. R-14 is the
more specific rule: it names P1 explicitly and states the intent, that a P1 is an organisation-wide outage
handled around the clock. R-13 is the general pause rule written for the ordinary queue, where no one works at
night. Keeping R-14 and rejecting the pause for P1 alone preserves the meaning of a P1; the alternative would
let the most severe incidents wait out a weekend inside their target, which is precisely the behaviour a P1
exists to prevent. The cost is real and accepted: an on-call rotation must cover P1s outside business hours.

**Service owner:** The Head of IT Service Delivery owns the major-incident policy and the on-call rota, so this
is that role's decision; the Service Desk Manager executes it but does not set the coverage.

**Customer outcome:** The whole organisation gets a P1 looked at within minutes of it being raised, at any hour
and on any day, instead of discovering on Monday that Friday's outage quietly sat inside its SLA.

## C2 - Closed tickets and reopening

**Decision:** A resolved or closed ticket can be reopened by the reporter within 7 days of its resolution or
closure; the reopen returns it to `in_progress` and clears `resolved_at` and `closed_at`. Outside that window,
or from any other state, a reopen is refused with 409, and further work needs a new ticket that references the
closed one through `related_to`.

**Rejected alternative:** Treating a closed ticket as permanently immutable, so that any reopen from `closed`
is refused regardless of age and every recurring problem becomes a new ticket.

**Reason:** R-09 and R-10 clash on the word "closed". Rejecting only the reopening of a closed ticket keeps
R-09 for everything else: a closed ticket cannot be edited, re-acknowledged or re-resolved, and no state other
than a deliberate reopen is allowed out of `closed`. The 7-day window bounds the exception, so the desk's
reports stay stable once a week has passed. R-10 states the customer-facing intent directly, that a fix which
did not work must be reopenable, and the same intent applies whether the agent had already closed the ticket or
not; forcing a duplicate ticket loses the link to the failed fix and hides the recurrence from reporting.

**Service owner:** The Service Desk Manager owns the closure and reopening policy, because that role sets what
counts as a finished ticket and what the desk does when a customer disagrees.

**Customer outcome:** A reporter whose problem comes back within a week can reopen the same ticket and have it
worked again without re-explaining the whole case or losing the history of the first attempt.

## C3 - VIP reporters and the priority matrix

**Decision:** Priority comes from the impact and urgency matrix, and then a ticket whose reporter is VIP is
raised to P2 if the matrix put it at P3 or P4; P1 and P2 are left untouched. Only the VIP flag moves a
priority, and only upward to that single floor.

**Rejected alternative:** Letting the matrix decide for everyone and storing the VIP flag without letting it
affect priority, which is what R-05 asks for when read as "the matrix and nothing else".

**Reason:** R-05 and R-06 contradict each other for a VIP ticket, so the minimal conflict is R-05's "and nothing
else" clause. Everything R-05 protects is kept: the matrix still sets the priority for the ordinary queue, the
client still cannot request a priority, and no field other than the VIP flag can move it. R-06 exists because a
leadership ticket that looks cosmetic by the matrix, for example a broken meeting-room screen for the executive
team, would otherwise sit at P4 and be buried, which is a business risk the desk has decided it cannot carry.
Capping the effect at P2 keeps the escalation narrow: a VIP ticket can never be pushed above what the matrix
says for a genuine P1 or P2.

**Service owner:** The Head of IT Service Delivery owns the escalation policy and is the role accountable for
deciding which reporters receive preferential treatment; the desk applies the policy at triage.

**Customer outcome:** The leadership and their teams always have their reported issues visible to the desk
within the P2 target, so a small-looking problem for a key reporter is not lost at the bottom of the queue.
