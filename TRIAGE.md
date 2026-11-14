---
lab5_triage:
  image: ghcr.io/psampir/itsm@sha256:5ea3f864ba2c9afe1313c9164ddf2141c0ede2c718a7b4df8b3c3c2f862f01e9
  sarif_receipt: 408
---
<!-- ai-generated: 60% - the rows and the Bake-off were drafted with an assistant from the run logs and bakeoff.json; the Dockerfile changes and every decision are mine -->
# Triage

What the gates and the reporting scanners found on my service, and what I did about each (CI-SPEC.md P-11, P-12).
Tool is the tool id of P-15. The rows below cover the seven fixable HIGH findings of the first image build (a
re-scan of the pre-Lab-5 image, kept here as evidence of what was fixed) and the two Semgrep rules that report on my
own code, outside `lab5-canary/`, in the receipted SARIF.

| Tool | Rule | Decision | Reason |
|---|---|---|---|
| trivy | CVE-2026-76844 | fix | zlib1g 1:1.3.dfsg+really1.3.1-1+b1 in Debian 13.7; `apt-get upgrade -y` in the Dockerfile brings 1:1.3.dfsg+really1.3.1-1+deb13u1 and the image gate is clean afterwards. |
| trivy | CVE-2026-85091 | fix | the second zlib1g HIGH, same package and same fixed version; covered by the same `apt-get upgrade -y` layer, verified by re-scanning the built image (0 fixable HIGH/CRITICAL). |
| trivy | CVE-2026-114613 | fix | msgpack 1.1.2 vendored inside pip/_vendor; pip is needed only to install, so the build now ends with `pip uninstall -y pip` and the package is no longer in the image. |
| trivy | GHSA-6v7p-g79w-8964 | fix | the same vendored msgpack 1.1.2 (advisory 1.2.1); removed from the runtime image with pip, so no .trivyignore entry was needed. |
| trivy | CVE-2025-47273 | fix | setuptools 70.3.0 vendored by pip as pip/_vendor/pkg_resources; `pip uninstall -y pip` removes it from the final image. |
| trivy | CVE-2026-97687 | fix | urllib3 2.7.0 inside pip/_vendor; removing pip in the same RUN layer takes it out of the image the gate scans. |
| trivy | CVE-2026-97689 | fix | the second urllib3 HIGH from pip's vendored copy, fixed by the same `pip uninstall -y pip`; the base image is also pinned by digest. |
| semgrep | dockerfile.security.missing-user.missing-user | fix | Dockerfile:23 - the image ran as root. It now creates uid 10001, chowns /app and /data, and ends with `USER svcdesk`; the service tests still pass 30/30 as that user. |
| semgrep | python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected | false-positive | docs/lab4/prom_mcp.py:34 - the URL is the operator's own `--prometheus-url` argument of a local, read-only MCP bridge; no request data reaches urllib, so the rule's premise does not hold. |

No `.trivyignore` or `.gitleaksignore` entry is needed: every gate is green on `main` without one, and a bare ignore
would fail `ignore-policy` anyway.

## Bake-off

Nine labelled defects under `lab5-canary/`, one matrix per tool from `bakeoff.json`. Trivy: TP 4, FP 0, FN 5,
precision 1.0000, recall 0.4444, F1 0.6154. Semgrep: TP 4, FP 2, FN 5, precision 0.6667, recall 0.4444, F1 0.5333.
gitleaks: TP 3, FP 0, FN 6, precision 1.0000, recall 0.3333, F1 0.5000. Grype and OSV-Scanner are identical at TP 2,
FP 0, FN 7, precision 1.0000, recall 0.2222, F1 0.3636 - both found the two vulnerable pins and nothing else.

Which detector goes in a gate. Trivy already sits in two of them (dependency files and the image), and on this set it
is the best combination of the two numbers: full precision and the highest recall, because it is the only tool that
reports both vulnerable pins, both credentials its secret scanner recognises, and still nothing on the three decoys.
gitleaks is the cheapest gate and the most trustworthy one here - three findings, three true positives, no false
alarm - so it earns its blocking slot. Semgrep is the only detector that saw the code classes: the weak hash (A01),
the disabled certificate check (A04) and the pickle sink (A10) are all Semgrep's. It also fired twice on decoys -
string-built SQL in `columns.py` and direct jinja2 use in `email_render.py` - which is exactly the precision 0.6667,
and the reason the course's pipeline keeps it report-only: as a gate on this set it would have blocked the canary for
two non-defects. Grype and OSV-Scanner add a second opinion on the vulnerability databases but no cell Trivy does not
already cover, so they belong in reporting, not in the gate.

What the matrix does not show. A03, the path-traversal in `attachment_read.py`, was found by none of the five: the
danger is in how the joined path is used, not in a pattern, and no scanner here follows the data flow into it. That is
the class of defect these gates cannot see at all, and it is why the canary's red run proves the gates are wired, not
that they are sufficient. Every recall here is an upper bound as well: the set is seeded, seeded defects flatter every
detector, and a real repository would show lower numbers against the same tools.
