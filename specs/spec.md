<!-- ai-generated: 80% - opencode drafted this specification from REQUIREMENTS.md and API.md; the three conflict resolutions (C1/C2/C3) and their reasoning were chosen and reviewed by the student -->

# svcdesk - service-desk API specification (Lab 1)

Status: specification, written and published **before any file under `src/`** (Core spec L1-CORE-5).
Sources of truth: `docs/REQUIREMENTS.md` (what the desk wants), `docs/API.md` (the enforced contract),
`docs/CHECKS.md` (the published checks). Where this document and `API.md` differ, `API.md` wins.

## 1. Purpose and scope

`svcdesk` is the ticketing HTTP API a four-hundred-person internal service desk runs on. It records tickets,
computes priority, keeps the SLA clocks, drives the ticket state machine, and refuses transitions that would
make the desk's reports wrong. It exposes JSON over HTTP on port 8080 and nothing else (R-01).

The implementation language is Python 3.13 with FastAPI, served by uvicorn, with SQLite for persistence. It
ships as a Docker Compose project built from the repository (R-22).

## 2. The three conflict resolutions

The requirements contain three pairs that cannot both hold. Each is resolved by rejecting the minimal
conflicting part of one requirement and keeping the rest of it. The service implements exactly the resolutions
below, and `DECISIONS.md` declares the same values (L1-CORE-4).

### C1 - SLA clock for P1: `wallclock`
P1 tickets have both targets on the wall-clock; P2 to P4 use the business-hours clock (section 8). This keeps
R-14 (a P1 runs around the clock) and rejects R-13's business-hours pause for P1 only. Consequence: a P1 raised
on Friday evening is late at 15 minutes past, not on Monday morning.

### C2 - closed tickets and reopening: `reopen`
Reopen is allowed from `resolved` and from `closed`, each within 7 days of the corresponding timestamp. This
keeps R-10 and rejects the "closed is immutable" part of R-09 for the single, time-boxed reopen action; a
closed ticket is otherwise final and any other work needs a new ticket with `related_to`.

### C3 - VIP reporters and the priority matrix: `vip`
Priority is the matrix value, then a VIP ticket at P3 or P4 is raised to P2; P1 and P2 are unchanged
(section 6). This keeps R-06 and rejects R-05's "the matrix and nothing else" for VIP reporters.

## 3. Ticket model

```
Ticket {
  id: string            opaque, unique, non-empty (UUID v4)
  title: string         1..200 characters, required
  description: string   0..4000 characters, optional (default "")
  reporter: { name: string (1..100), email: string | null, vip: boolean (default false) }
  impact: 1 | 2 | 3     required integer (1 = whole organisation, 2 = a team, 3 = one person)
  urgency: 1 | 2 | 3    required integer (1 = work stopped, 2 = degraded, 3 = cosmetic)
  priority: "P1"|"P2"|"P3"|"P4"   computed by the service, never accepted from the client
  state: "new"|"acknowledged"|"in_progress"|"resolved"|"closed"
  created_at, acknowledged_at, resolved_at, closed_at: instants or null until the event happened
  related_to: string | null   optional on create; not validated in Lab 1
  sla: { ack_due_at: instant, resolve_due_at: instant }
}
```

Server-owned fields sent by a client (`id`, `priority`, `state`, the four timestamps, `sla`) and unknown
fields are silently ignored, never an error (R-20). Instants are reported in UTC with a `Z` suffix (R-17) and
compared as points in time.

## 4. HTTP interface

| method and path | success | notes |
|---|---|---|
| `GET /health` | 200 `{"status":"ok","service":"svcdesk"}` | extra fields allowed (R-02) |
| `POST /tickets` | 201 Ticket | validation error: 400/422 with a top-level `error` (section 5) |
| `GET /tickets` | 200 `[Ticket]` | optional exact-match filters `?state=` and `?priority=`; one array, no pagination, any order (R-19) |
| `GET /tickets/{id}` | 200 Ticket | 404 with `error` if unknown (R-25) |
| `GET /tickets/{id}/sla` | 200 SLA report (section 9) | 404 with `error` if unknown (R-15) |
| `POST /tickets/{id}/ack` `/start` `/resolve` `/close` `/reopen` | 200 Ticket | 409 on an invalid transition, 404 if unknown (R-07, R-08) |
| unknown path | 404 with a JSON `error` body | a wrong method on a known path may answer 404 or 405 |

All bodies are `application/json`. Successful actions return 200 with the full ticket.

## 5. Validation and error contract

- `title` required, 1..200 characters; `description` optional, at most 4000; `reporter.name` required, 1..100;
  `impact` and `urgency` required integers in 1..3 (a string such as `"high"` is an error) (R-03, R-20).
- On any validation error: **400 or 422** with a JSON body carrying a top-level `error` object (R-20).
- Unknown ticket id and unknown path: **404** with a JSON `error` object (R-25).
- Invalid transition: **409** with a JSON `error` object (R-08).
- A malformed `X-Test-Clock` header: **400 or 422** (R-21).

## 6. Priority

The matrix (R-04) is the starting point (impact down, urgency across):

| impact \ urgency | 1 | 2 | 3 |
|---|---|---|---|
| **1** | P1 | P2 | P3 |
| **2** | P2 | P3 | P4 |
| **3** | P3 | P4 | P4 |

Under C3 = `vip`, after the matrix a ticket with `reporter.vip = true` whose priority is P3 or P4 is raised to
P2; P1 and P2 are unchanged (R-06). A `priority` field in the request body is always ignored (R-05).

## 7. State machine and reopen window

| action | endpoint | from | to | side effect |
|---|---|---|---|---|
| acknowledge | `/ack` | new | acknowledged | `acknowledged_at = now` |
| start | `/start` | acknowledged | in_progress | - |
| resolve | `/resolve` | in_progress | resolved | `resolved_at = now` |
| close | `/close` | resolved | closed | `closed_at = now` |
| reopen | `/reopen` | resolved, or closed (C2 = `reopen`) | in_progress | clears `resolved_at` and `closed_at` |

Every other transition returns 409. Reopen is allowed while `now <= resolved_at + 7 days` (from `resolved`) and
while `now <= closed_at + 7 days` (from `closed`); outside the window, or from any other state, it is 409
(R-10, R-11). Reopening does not change `sla.ack_due_at` or `sla.resolve_due_at` (R-11).

## 8. SLA clock

Targets (R-12):

| priority | acknowledge within | resolve within |
|---|---|---|
| P1 | 15 min | 4 h |
| P2 | 1 h | 8 h |
| P3 | 4 h | 24 h |
| P4 | 8 h | 72 h |

**Wall-clock target** = `created_at + target`.

**Business-hours target** counts only time inside business hours: Monday to Friday, the half-open window
`[08:00:00, 16:00:00)` in `Europe/Warsaw` (DST-aware; public holidays are business days) (R-13). Algorithm:
convert `created_at` to `Europe/Warsaw`; if it is outside a business window, move forward to the next opening
(08:00 of the next business day, or 08:00 today if before opening); consume the target from consecutive
business windows; **a target that ends exactly at closing time is due at 16:00:00 that day, not 08:00 the next
day** (the tie rule); convert the due instant back to UTC.

Which clock applies:

- C1 = `wallclock`: P1 uses the wall-clock for both targets; P2 to P4 use the business-hours clock.
- (The rejected C1 = `business` would put every priority on the business-hours clock.)

`ack_due_at` and `resolve_due_at` are computed at creation and stored; they do not change afterwards
(R-11, R-16). The eight test vectors in `API.md` section 4 (T1..T8) are reproduced exactly; the checks cover
T1, T2, T3 (wall-clock pair), T4, T5 and T7.

## 9. Breach and pause

`GET /tickets/{id}/sla` returns `{ priority, ack_due_at, resolve_due_at, ack_breached, resolve_breached,
paused }`, evaluated at `now` (the request clock, else real UTC time) (R-15, R-16):

- `ack_breached` = (not acknowledged and `now > ack_due_at`) or (`acknowledged_at > ack_due_at`).
- `resolve_breached` = (not resolved and `now > resolve_due_at`) or (`resolved_at > resolve_due_at`); a
  reopened ticket counts as not resolved again, against its original `resolve_due_at`.
- Reaching the due instant exactly is **not** a breach.
- `paused` = ticket not resolved or closed, its resolution target runs on the business-hours clock, and `now`
  is outside a business window. Under C1 = `wallclock`, a P1's targets are wall-clock, so a P1 is never paused;
  P2 to P4 can be paused.

## 10. Test clock

When `SVCDESK_TEST_CLOCK` is `1` or `true`, a request may carry an `X-Test-Clock` header with an RFC 3339
instant that includes an offset (`Z` recommended). For that request only, that instant is `now`: it sets
`created_at`, `acknowledged_at`, `resolved_at` and `closed_at`, and is the reference for breach, pause and the
reopen window (R-21). A naive timestamp is malformed and returns 400/422. The service never compares one
request's clock with another's and never enforces monotonic time. Without the header, `now` is real UTC time;
when the variable is unset or `0`, the header is ignored.

## 11. Compose and runtime contract

At the repository root, `docker-compose.yml` defines (R-22, R-24):

- a service named exactly `svcdesk` with a `build:` key (context inside the repository; never `image:` alone),
  listening on port 8080 inside the container, with `SVCDESK_TEST_CLOCK: "1"`;
- no host-path bind mounts on any service (named volumes and `tmpfs` are fine);
- a named volume `svcdesk-data` mounted at `/data`;
- a healthcheck so `docker compose up --wait` is reliable; `GET /health` answers 200 within 120 s of `up`;
- images that need no network at run time: dependencies are installed at build time.

## 12. Persistence

Tickets are stored in SQLite at `/data/svcdesk.db` inside the named volume, so they survive a restart of the
`svcdesk` container (R-23).

## 13. Requirement traceability

| req | where addressed |
|---|---|
| R-01 | HTTP JSON API, port 8080 (sections 4, 11) |
| R-02 | `GET /health` (section 4) |
| R-03 | Ticket model (section 3) |
| R-04 | Priority matrix (section 6) |
| R-05 | priority computed server-side, request field ignored (section 6) |
| R-06 | C3 = `vip` floor at P2 (section 6) |
| R-07 | state machine (section 7) |
| R-08 | 409 on invalid transition, 404 unknown (sections 5, 7) |
| R-09 | closed is final except the C2 reopen (section 7) |
| R-10 | reopen within 7 days, from resolved and closed (section 7) |
| R-11 | reopen does not change the due instants (sections 7, 8) |
| R-12 | SLA targets (section 8) |
| R-13 | business-hours clock for P2-P4 (section 8) |
| R-14 | C1 = `wallclock`: P1 around the clock (section 8) |
| R-15 | `GET /tickets/{id}/sla` (section 9) |
| R-16 | breach and pause rules (section 9) |
| R-17 | UTC `Z` instants (sections 3, 4) |
| R-18 | opaque UUID id (section 3) |
| R-19 | `GET /tickets` filters, no pagination (section 4) |
| R-20 | validation and error body (section 5) |
| R-21 | test clock (section 10) |
| R-22 | compose contract (section 11) |
| R-23 | SQLite persistence (section 12) |
| R-24 | `up --wait` and `/health` within 120 s (section 11) |
| R-25 | 404 JSON for unknown path and id (section 5) |
