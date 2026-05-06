# Dashboard Stage Detail Completion

## Goal

Complete the dashboard stage-detail slice so every pipeline stage can show its Markdown artifact and the LLM inference tab shows normalized, stage-filtered, full request/response records.

## Scope

- Extend metrics artifact lookup to all six built-in stages.
- Prefer Markdown paths recorded in `run.json`, falling back to conventional filenames.
- Normalize LLM trace records across legacy intake/solution files and multi-turn code/test/review files.
- Persist per-turn request audit files for code generation, test generation, and code review.
- Write local `requirement.md` after requirement analysis succeeds and record `requirement_markdown`.
- Keep dashboard API routes unchanged while adding response fields.
- Reset the stage detail tab to artifact view when the selected stage changes.

## Verification

- Add focused metrics and pipeline/agent tests.
- Run targeted backend unit tests.
- Run `uv run python -m compileall devflow`.
- Run dashboard build from `dashboard/`.

