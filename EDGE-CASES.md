---
lab2_edge_cases:
  E1: {rule: R-08, count: 3}
  E2: {rule: R-06, count: 2}
  E3: {rule: R-09, count: 4}
  E4: {rule: R-10, count: 4}
  E5: {rule: R-12, count: 1}
  E6: {rule: R-13, count: 11}
---
<!-- ai-generated: 70% - opencode drafted the structure and the counts from my service's output; the reasoning is mine, edited by hand -->

# Edge cases in the practice event log

The six counts above are what **my own service** reports for `fixtures/events-practice.jsonl`
over the published window. They come from `POST /dora/metrics`, not from reading the file by
eye; the consistency between this file and the running service is the point of `L2-CORE-4`.

## E1 - clock skew produces a negative lead time

- What the log contains: three successful production deployments shipped a commit whose `commit.at` is later than the deployment's own `at`: `sha-0040` by `DEP-0012` (about 14 minutes), `sha-0094` by `DEP-0024` (51 seconds) and `sha-0123` by `DEP-0031` (13 minutes). The two clocks disagreed, so the arithmetic lead time is negative.
- What a default definition would have done: a naive median would either drop the three pairs to keep the median "sensible", or include the raw negative numbers, which drags the median down and makes the delivery pipeline look faster than it can possibly be.
- Why the rule is defensible: a lead time cannot be negative - a change cannot reach production before it exists - so the honest correction is to clamp the impossible value to zero and count it, not to delete the evidence. The count is exposed as `anomalies.negative_lead_time_pairs`, so a dashboard reader can see that three timestamps are untrustworthy instead of being silently flattered.

## E2 - a revert of a revert

- What the log contains: `sha-0071` reverts `sha-0070`, which itself reverts `sha-0069` (`change_id CHG-0033`). Both revert commits carry `change_id: null`; only the original carries a change id.
- What a default definition would have done: treating each commit as its own unit of work would count three commits and three changes, so a single change that was reverted and then restored would inflate every throughput number threefold and split one lead time into three.
- Why the rule is defensible: change identity should follow the work, not the churn. Resolving revert chains transitively means a change is counted once no matter how many times it is undone and redone, so `counts.changes` and the ground-truth medians measure deliveries rather than Git noise. `anomalies.revert_chains_collapsed: 2` makes the collapsing visible.

## E3 - a hotfix that never touched `main`

- What the log contains: four commits reached production from hotfix branches rather than `main`: `sha-0019` (`hotfix/2609`), `sha-0077` (`hotfix/4347`), `sha-0108` (`hotfix/6085`) and `sha-0127` (`hotfix/1544`). They are ordinary commits with ordinary change ids, carried by real production deployments.
- What a default definition would have done: a definition that filters on `branch == "main"` would throw all four away, understating deployment throughput and claiming a change was never delivered when it plainly was.
- Why the rule is defensible: `branch` is free text with no privileged meaning; production is the source of truth. A hotfix that customers felt is a delivery, so it must count, and `anomalies.commits_never_on_main: 4` records how much of the delivery flow bypassed the mainline.

## E4 - a deployment with zero linked commits

- What the log contains: four in-window production deployments carry an empty `commits` list (`DEP-0026`, `DEP-0032`, and the failed `DEP-0043` and `DEP-0044`). A deploy can ship an empty commit set - a config roll, a re-run, a manual promotion.
- What a default definition would have done: code that assumes a deployment always has commits might drop the deployment, or divide by the wrong denominator, or crash on an empty list. Dropping them would also quietly change the failure and rework rates.
- Why the rule is defensible: a deployment is a deployment; it still happened and still carries release risk. Keeping them in the frequency, fail-rate and rework denominators but contributing no lead-time pairs is the only treatment that keeps each metric's denominator honest. `anomalies.deployments_without_commits: 4` lets a reader discount frequency that was padded with empty deploys.

## E5 - a deployment that failed and never recovered

- What the log contains: `DEP-0015` failed on 2026-09-07 and is covered by `INC-0004`, which was opened but never resolved. There is no recovery instant anywhere in the log.
- What a default definition would have done: a naive implementation would close the incident at the window's end and invent a recovery time, or drop the failure entirely - lowering the recovery median and hiding an outage that was still open when the window closed.
- Why the rule is defensible: recovery time should measure recovery, and none happened. Excluding the open failure from the median, counting it in `counts.open_failures` and still charging it to `change_fail_rate` is the honest reading: the instability is real, but no duration can be claimed for it.

## E6 - overlapping incidents

- What the log contains: several incidents in the window overlap in time - one incident can cover more than one failed deployment, and different incidents' `[opened, resolved)` intervals intersect, giving 11 overlapping pairs in the practice set.
- What a default definition would have done: merging overlapping incidents, or summing their wall-clock durations, would double-count the same minutes of outage and credit a single recovery event to several incidents, distorting both the recovery median and any downtime total.
- Why the rule is defensible: recovery is computed per failed deployment, through that deployment's earliest covering incident, so an incident that covers two failures gives both the same instant and no time is merged or added. `anomalies.overlapping_incident_pairs: 11` warns that incident timelines are not a tidy sequence and should not be read as a simple sum.

## Gaming demonstration

I improved `deployment_frequency_per_day` by exploiting rule **R-11**, and I did it in the
two ways the conservation rule R-19 still allows. First I added 24 brand-new production
deployments with an empty `commits` list. R-10 says a deployment with no commits is not
excluded from deployment frequency, so each one counts as a release even though it shipped
nothing at all. That alone lifted the frequency from 2.0 to about 2.71 deployments per day,
a 36 % improvement, comfortably past the 25 % margin in R-20. Second, I moved every base
deployment three days later, which R-19 permits because a base deployment may be moved later
but never earlier.

The five-metric dashboard now looks excellent: more deployments per day, a lower change
fail rate and a lower rework rate, simply because the denominator grew. The damage is
invisible in those five numbers but real, and that is exactly why the lab also reports
ground truth: measured over the work that was already there (the checker strips out my
added commits and scores only the base shas), the true change lead time rose from 539 452
seconds to 791 959 seconds - 147 % of the original - and the number of changes actually
delivered fell from 65 to 58. Throughput went up on the dashboard while delivery got slower
and thinner. Had I only added empty deploys, nothing real would have been harmed and R-21
would have caught the game; it was delaying the genuine work that made delivery measurably
worse.

The incentive that produces this in a real team is a target attached to a single throughput
metric. If a platform team is rewarded for "deployments per day", the cheapest way to hit the
number is to cut the size of releases and re-run or re-clear empty deploys, and the second
cheapest is to batch real changes behind an artificial freeze so each release looks bigger.
The people rewarded are the ones who report the number, not the ones who deliver - engineering
managers and release managers whose dashboards turn green, while the person waiting on a fix
experiences a 150 % longer lead time. This is Goodhart's law with arithmetic attached: once
deployment frequency becomes a target, it ceases to be a good measure, and the ground truth is
what reveals the switch.
