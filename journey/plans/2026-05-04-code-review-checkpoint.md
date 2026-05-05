# Code Review Checkpoint Implementation Plan

## Goal

Implement the fifth DevFlow node, `code-review-agent`, as the second Human-in-the-Loop checkpoint after test generation.

## Implementation

- Add `devflow.review` with schema constants, prompt construction, read-only review tools, artifact validation/writing, LLM review loop, and Markdown rendering.
- The review artifact uses `schema_version = "devflow.code_review.v1"` and records upstream inputs, review status, quality gate, findings, test summary, diff summary, repair recommendations, tool events, and Chinese summary/warnings.
- Expose `devflow review generate` for manual execution from a run id or explicit upstream artifacts.
- Wire successful `test_generation` to execute `code_review`.
- Write `code-review.json` and `code-review.md` in the run directory.
- Create a `code_review` checkpoint after review generation and preserve the prior solution checkpoint in `checkpoint_history`.
- Support `Approve <run_id>` and `Reject <run_id>` based on `checkpoint["stage"]`.
- On blocking review findings, automatically run one repair cycle by injecting review feedback into code generation, then rerun test generation and review.
- Keep downstream `delivery` pending.

## Tests

- Unit tests for review input validation, read-only tool enforcement, LLM review loop, failed-test blocking behavior, Markdown rendering, and CLI output.
- Pipeline tests for solution approval running code, test, and review; review checkpoint publication; one automatic repair attempt; and checkpoint decisions branching by stage.

## Verification

Run:

```powershell
uv run pytest tests/test_code_review.py tests/test_test_generation.py tests/test_code_generation.py tests/test_pipeline_start.py tests/test_checkpoint.py -q -p no:cacheprovider
uv run python -m compileall devflow
```

## Assumptions

- Code review can read files and run safe checks but must not edit workspace files directly.
- Blocking issues include correctness, security, failed tests, missing required tests, and requirement mismatch.
- Style-only comments are non-blocking.
- v1 allows one automatic repair attempt before escalating to a human checkpoint.
