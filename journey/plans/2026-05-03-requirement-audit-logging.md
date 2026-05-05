# Requirement Intake Audit Logging Plan

## Goal

Add run-local audit logging for the `requirement_intake` stage. The trace must capture data-link events, LLM request/response payloads, token usage when provider-supplied, timing, artifact writes, reply attempts, and failures.

## Implementation

- Add `devflow.trace` with `RunTrace` and `StageTrace` helpers that append structured events to `trace.jsonl` and write large JSON audit payloads into the run directory.
- Extend `devflow.llm` with `chat_completion(...)` returning rich completion metadata while keeping `chat_completion_content(...)` compatible.
- Thread an optional stage trace through the pipeline requirement artifact builder so `devflow start` can write LLM audit files during the requirement stage.
- Add an `audit` section to `run.json` with trace paths and compact token usage summary.

## Tests

- LLM rich result preserves raw response and usage.
- Missing provider usage is recorded as missing, not estimated.
- Audit files do not include API keys or Authorization headers.
- Successful pipeline runs write trace and LLM audit files.
- Failure paths append trace events before the failed run is finalized.
- Heuristic analyzer writes stage events without LLM payload files.
