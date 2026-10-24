<!-- ai-generated: 75% - opencode drafted the comparison from the two ledgers and the queries I re-ran on the snapshot; I wrote the conclusion -->

# Two investigators on the same incident

The first investigator is the recorded run shipped with the recording: the course agent loop `agent.py` with
`qwen3:4b-instruct` behind it, working from the question "Checkout errors paged at 06:39:19Z on 2026-10-12.
Investigate 06:30Z to 06:50Z. What is the cause?". The second is the same loop and the same MCP server with a local
`qwen3-vl-8b` on llama.cpp, asked the same question against the same served snapshot, so the two transcripts differ
only in the model.

**Where they agreed.** Both went straight to checkout's errors, both found payment's `Charge` span as the failing
dependency, and both connected it to checkout's `PlaceOrder`. The recorded investigator got there with four tool
calls and no detours; the local model found the same call path but spent its first steps on label discovery and then
misread a lowercase `span_kind="client"` as "no data", which is the error the ledger scores as `hallucinated`.

**Where they parted.** The recorded run made three separate, confident statements about the payment span and the
downstream failure, all of them correct against the snapshot: payment's error counter rises to 8, checkout's failure
ratio to 20 % of the orders in the window. The local run made one correct statement about checkout's errors, one
correct statement about which spans carry them, one false statement about the latency histogram, and then hedged:
"unclear if the issue was due to timeouts, resource constraints, or external service failures". That hedge is what
makes its last entry `partially_correct` rather than `correct` - the component is right, the mechanism is not
established, and the premise it leaned on (no duration data) is contradicted by the snapshot.

**What the data proved.** The snapshot settles every disagreement in favour of the recorded run: the duration
histogram exists and is positive at 06:41 (the local model's `hallucinated` entry), and payment's failures are real
and predate nothing (both runs' `correct` entries). The local model's weakness is not its reasoning about the metric
it did read but its tool hygiene: it never retried the label case and never queried the payment side after the first
error count. On this evidence the recorded investigator is the better instrument for this incident, and the local
one is useful only with a human re-running its queries - which is the discipline the ledger imposes anyway.
