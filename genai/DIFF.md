---
lab3_genai_diff:
  instrumentation: "opentelemetry-instrumentation-genai-openai 1.2b0 (opentelemetry-sdk 1.45.0, openai 3.19.2) against a local llama.cpp OpenAI-compatible endpoint"
  spec_ref: "semantic-conventions-genai@e57c543b4889619eb2a05702471937db5119165d"
  attributes:
    - {name: gen_ai.operation.name, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.provider.name, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.request.max_tokens, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.request.model, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.request.temperature, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.response.finish_reasons, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.response.id, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.response.model, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.usage.input_tokens, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.usage.output_tokens, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.request.top_p, emitted: false, in_spec: true, stability: development}
    - {name: gen_ai.request.stop_sequences, emitted: false, in_spec: true, stability: development}
    - {name: gen_ai.response.time_to_first_chunk, emitted: false, in_spec: true, stability: development}
    - {name: gen_ai.input.messages, emitted: false, in_spec: true, stability: development}
    - {name: gen_ai.system, emitted: false, in_spec: false}
---
<!-- ai-generated: 65% - opencode drafted the capture script and this diff; I ran the call against my local llama.cpp model and checked every claim against the pinned registry -->

# What the library emits, against the spec

The call was one `client.chat.completions.create` against a local llama.cpp server (`qwen3-vl-8b`), made with
`OpenAIInstrumentor().instrument()` from `opentelemetry-instrumentation-genai-openai` 1.2b0 and exported with
`opentelemetry-exporter-otlp-json-file` 0.66b0 into `genai/spans.json`. One span, `chat qwen3-vl-8b`, kind
`CLIENT`, with ten `gen_ai.*` attributes.

**What agrees with the spec.** All ten emitted keys are attributes of `semantic-conventions-genai` at the pinned
commit, and every one of them is stability `development` there - the new repository has not promoted any GenAI
attribute past development since it split out of the main semantic conventions. The important ones are right: the
operation discriminator (`gen_ai.operation.name = chat`) and the provider discriminator
(`gen_ai.provider.name = openai`, which is what the client is configured to speak) carry the meaning the spec gives
them, `gen_ai.request.model` and `gen_ai.response.model` both name `qwen3-vl-8b`, and the token counts land in
`gen_ai.usage.input_tokens` (29) and `gen_ai.usage.output_tokens` (26), the new names, not the older
`gen_ai.usage.prompt_tokens`/`completion_tokens` pair.

**What does not.** The library emits only the request settings it sees on the wire, so a dashboard that wants
`gen_ai.request.top_p` or `gen_ai.request.stop_sequences` finds nothing here: I did not set them, and a client-side
instrumentation cannot invent them. `gen_ai.response.time_to_first_chunk` is absent for a stronger reason - it is a
streaming attribute and this call was not streamed. The interesting absence is `gen_ai.system`: the older
conventions (and the older `opentelemetry-instrumentation-openai-v2` package) put the provider there, and the pinned
ref no longer defines the key at all, so a dashboard still grouping by `gen_ai.system` would find an empty panel
against a modern library. The library also adds three non-`gen_ai.*` attributes - `server.address`, `server.port`
and `openai.response.system_fingerprint` - which the GenAI conventions do not govern and which I left out of this
diff.

**What it means for a dashboard.** Cost and latency panels can be built on this library alone: tokens per request
from `gen_ai.usage.*`, the model split from `gen_ai.response.model`, and the operation split from
`gen_ai.operation.name`. The dashboards cannot rely on prompt or completion content - `gen_ai.input.messages` and
`gen_ai.output.messages` are not emitted by default, which is the behaviour the conventions want for privacy - nor on
the provider under its old name. Anything that needs a request parameter has to be captured at the call site, because
the wire only carries what the application sent.
