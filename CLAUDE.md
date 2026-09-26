# CLAUDE.md

Project guidance for AI coding agents working on the `svcdesk` repository (Lab 1 of the ITSM course).

## What this repository is

`svcdesk` is a small service-desk HTTP API (tickets, priority, SLA clocks, state machine) built with Python
3.13, FastAPI and SQLite, shipped with Docker Compose. The enforced contract is `docs/lab1/API.md`; the requirements
are `docs/lab1/REQUIREMENTS.md`; the published checks are `docs/lab1/CHECKS.md`. Where documents differ, `docs/lab1/API.md`
wins.

## Decisions already made (do not silently change them)

- C1 = `wallclock` - P1 uses the wall-clock; P2 to P4 use the business-hours clock.
- C2 = `reopen` - a closed ticket can be reopened within 7 days.
- C3 = `vip` - a VIP ticket at P3 or P4 is raised to P2.

These are declared in `DECISIONS.md` and matched by the running service (L1-CORE-4).

## Working rules

- Specs before code: the specification under `specs/` is receipted before any file under `src/` is committed.
- No network at run time; dependencies are installed at build time (`requirements.txt`).
- No host-path bind mounts anywhere; use the named volume for the SQLite file.
- Run `./itsmlab.sh verify 1` before claiming anything works; exit code 0 is the only acceptable result for Core.

## Sub-agents

See `.claude/agents/` and `AGENT-POLICY.md`. Agents are given a narrow denylist so their blast radius is
bounded: a reviewer that reads and comments must not delete, push, run containers, or fetch the network.
