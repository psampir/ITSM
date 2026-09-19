<!-- ai-generated: 70% - opencode drafted this convergence report from the specification and the implementation; reviewed by the student -->

# svcdesk - specification to implementation convergence (Lab 1)

This file compares the written specification (`specs/spec.md`) with what was actually built in `src/`, as the
spec-kit `converge` step would report. It records where the implementation matches the specification and where
the specification was deliberately more precise than the checks require.

## Decisions

The specification fixed C1 = `wallclock`, C2 = `reopen`, C3 = `vip`. The running service exhibits exactly these
values: `GET /tickets/{id}/sla` for a P1 created Friday 17:00 returns the wall-clock pair, a closed ticket
reopens within 7 days, and a VIP ticket at impact 3 / urgency 3 is raised to P2. The checker observed
`C1=wallclock C2=reopen C3=vip`, matching `DECISIONS.md`.

## Requirements checked

- **R-01 / R-02**: the API is JSON over HTTP on port 8080 and `GET /health` answers
  `{"status":"ok","service":"svcdesk"}`. Implemented and covered by the self-tests.
- **R-04 / R-05 / R-06**: the priority matrix, the server-side computation, and the C3 VIP floor at P2. The
  matrix is a constant table in `src/svcdesk/main.py`; the matrix, the VIP bump, and the ignored `priority`
  field are all exercised by the self-tests.
- **R-10 / R-11**: the 7-day reopen window from both `resolved` and `closed`, and the fact that reopen does not
  move the SLA due instants. Implemented in the `reopen` route; the due instants are stored at creation and
  never recomputed.
- **R-12 / R-13 / R-14**: the four SLA targets, the business-hours clock, and the P1 wall-clock exception. The
  business-hours algorithm in `src/svcdesk/sla.py` reproduces the published vectors T1, T2, T3 (wall-clock
  pair), T4, T5 and T7 to the second, including the tie rule for T4.
- **R-15 / R-16**: the SLA report with breach and pause. Pause is reported only for the business-hours clock,
  so a P1 is never paused under C1 = `wallclock`.
- **R-20 / R-25**: validation and the top-level `error` object on 400/422/404/409.
- **R-22 / R-23 / R-24**: the compose contract, SQLite persistence in a named volume, and `up --wait` with a
  healthcheck.

## Convergence result

Every requirement the specification states is realised in `src/svcdesk/`. No requirement is unimplemented, and
no behaviour in the code contradicts the ten declarations above. The three conflict resolutions are the only
places where a requirement is deliberately not honoured, and each rejection is the minimal one recorded in
`DECISIONS.md`.
