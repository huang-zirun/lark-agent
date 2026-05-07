# Dashboard Root Fixes Implementation Plan

## Goal

Fix the dashboard provider display, stage artifact scrolling, center stage scrolling, and LLM expansion persistence from their data contract and layout roots rather than with ad-hoc DOM patches.

## Scope

- Update LLM audit payloads so new runs record the real provider and model.
- Update metrics parsing so provider means real LLM provider, with compatibility for older artifacts.
- Update the zero-build dashboard under `devflow/dashboard/dist/` only.
- Add focused tests for the backend provider contract and metrics compatibility behavior.

## Steps

1. Add failing tests in `tests/test_llm.py` and `tests/test_metrics.py` for real provider propagation and legacy provider fallback.
2. Extend `devflow.llm.LlmCompletion` audit payload with `provider`, `model`, and optional `base_url_host`, while preserving `usage_source`.
3. Update `devflow.metrics` to prefer response provider, then stage artifact metadata `llm_provider`, then `run.provider_override`.
4. Update dashboard CSS so center and right panels are stable scroll containers with `min-height: 0` and full-height flex content.
5. Update dashboard JS so LLM call and prompt expansion state survives polling re-renders and is scoped by run/stage/call.
6. Run `uv run pytest tests/test_llm.py tests/test_metrics.py -q -p no:cacheprovider`.

## Acceptance Criteria

- Stage cards and LLM trace show real providers such as `mimo`, not the literal usage source value `provider`.
- Old runs without response `provider` still show a best-effort provider from stage artifact metadata or run override.
- Right-side stage artifact and LLM tabs scroll through long content.
- Center stage list scrolls as a stable panel without permanently hiding the top state.
- Expanded LLM calls and prompt sections remain expanded after polling refreshes.
