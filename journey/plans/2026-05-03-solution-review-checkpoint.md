# Solution Review Checkpoint Plan

Date: 2026-05-03

## Goal

Add the first DevFlow human review checkpoint after `solution_design`: the runtime writes a local technical solution, asks the user to approve or reject it, and only records continuation after approval.

## Implementation

- Add `devflow.checkpoint.v1` as `checkpoint.json` in each run directory after solution design.
- Render every solution artifact to a human-readable `solution.md` with summary, file changes, API design, tests, risks, and review checklist.
- If no workspace can be resolved, mark `solution_design` as `blocked`, write a blocked checkpoint, and ask the bot user to provide `仓库：...` or `新项目：...`.
- Route incoming bot messages through checkpoint handling first:
  - approve messages update the checkpoint to `approved` and record the request to continue.
  - reject messages without a reason set the checkpoint to `awaiting_reject_reason` and ask the user for details.
  - the next message from the same chat and sender captures the reject reason, marks the previous attempt rejected, and reruns `solution_design`.
- Keep card actions presentation-only in v1 because local `lark-cli` exposes message events but not card button callbacks.

## Verification

- Add focused checkpoint unit tests for command parsing, state transitions, card construction, and markdown rendering.
- Extend pipeline tests for blocked workspace, review checkpoint publication, approve flow, reject two-turn flow, and solution attempt incrementing.
- Run focused tests:
  `uv run pytest tests/test_checkpoint.py tests/test_pipeline_start.py tests/test_solution_design.py -q`
- Run full regression:
  `uv run pytest`

## Assumptions

- Reject reruns `solution_design`, not requirement intake.
- `code_generation` remains pending; approval records a continuation request but does not implement code generation.
- Runtime continues to use only Python standard library dependencies.
