# Solution LLM Timeout Root Fix Plan

## Goal

Fix solution-design LLM hangs at the root by enforcing a total wall-clock timeout for real LLM calls and by making blocked-run solution resume use the same state, trace, notification, artifact, and failure handling path as the initial solution-design stage.

## Tasks

- Add failing tests for:
  - real HTTP LLM calls timing out by total wall-clock duration;
  - solution-design request audit being written before the LLM call and failure being traced;
  - blocked workspace resume persisting solution-design failure instead of bubbling the exception.
- Implement a stdlib-only hard timeout in `devflow.llm` for unpatched real network calls while preserving injected opener behavior for tests.
- Expose a reusable LLM request-body builder and use it for pre-call solution request auditing.
- Extract a shared solution execution helper in `devflow.pipeline` and delegate both initial and blocked-resume solution paths to it.
- Update project memory after verification.

## Verification

- `uv run python -m unittest tests.test_llm tests.test_solution_design tests.test_pipeline_start tests.test_stage_notifications`
- `uv run python -m unittest discover tests`
