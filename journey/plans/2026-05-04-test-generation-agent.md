# Test Generation Agent Implementation Plan

## Goal

Implement the fourth DevFlow node, `test-generation-agent`, for the "测试生成" stage described in `docs/功能一.md`.

## Implementation

- Add `devflow.test` with schema constants, prompt construction, runner detection, artifact validation/writing, a small LLM tool loop, test command capture, and diff capture.
- Prefer existing test frameworks instead of vendoring external test-generation repositories:
  - Python: detect pytest/unittest and prefer `uv run pytest`.
  - JavaScript/TypeScript: detect `package.json` scripts and common Vitest/Jest dependencies.
  - Java: detect Maven/Gradle build files.
- Expose `devflow test generate` for manual execution from a run id or explicit requirement/solution/code-generation artifacts.
- Wire successful `code_generation` to run `test_generation` automatically.
- Write `test-generation.json` and `test.diff` in the run directory.
- Keep downstream `code_review` and `delivery` as pending.

## Tests

- Unit tests for test-generation artifact validation, runner detection, LLM tool loop, command execution capture, CLI output, and workspace-boundary reuse.
- Pipeline tests for approval triggering both code generation and test generation.
- Pipeline failure test proving a test-generation failure records `test_generation` as failed while preserving the code-generation artifact.

## Verification

Run:

```powershell
uv run pytest tests/test_test_generation.py tests/test_code_generation.py tests/test_pipeline_start.py -q -p no:cacheprovider
uv run python -m compileall devflow
```

## Assumptions

- Test generation may write test files inside the approved workspace.
- v1 does not install dependencies automatically.
- Optional generators such as CoverUp, Pynguin, and EvoSuite are adapter candidates, not bundled dependencies.
- Deep framework-specific generation beyond Python/JS/Java runner detection remains future work.
