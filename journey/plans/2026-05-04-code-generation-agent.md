# Code Generation Agent Implementation Plan

## Goal

Implement the third DevFlow node, `code-generation-agent`, after solution approval.

## Implementation

- Add `devflow.code` with schema constants, prompt construction, file tools, permission checks, diff capture, and a small LLM tool loop.
- Add `devflow code generate` for manual execution from `solution.json` or `--run`.
- Wire approved solution checkpoints to run `code_generation` immediately instead of only recording a continuation request.
- Write `code-generation.json` and `code.diff` in the run directory.
- Keep downstream `test_generation`, `code_review`, and `delivery` as pending.

## Tests

- Unit tests for workspace-boundary enforcement, file tools, LLM tool loop, artifact contract, and diff capture.
- CLI test for manual `devflow code generate`.
- Pipeline tests for bot checkpoint approval and CLI approval triggering code generation.

## Verification

Run:

```powershell
uv run pytest tests/test_code_generation.py tests/test_pipeline_start.py tests/test_checkpoint.py -q -p no:cacheprovider
uv run pytest tests -q -p no:cacheprovider
```

## Assumptions

- Approval of the solution means DevFlow may write inside the resolved workspace.
- Code generation v1 does not run package installs or create commits.
- LLM failures fail the `code_generation` stage and leave existing workspace changes in place for audit.
