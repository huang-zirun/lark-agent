# Workspace Blocked Guidance Plan

Date: 2026-05-03

## Goal

Make the bot response actionable when `devflow start` completes requirement intake but cannot enter solution design because no local workspace context was provided.

## Implementation

- Update the blocked workspace reply to explain that technical solution design needs a locally accessible codebase context.
- Tell the user the run is paused at `solution_design` until they reply with exactly one workspace directive line.
- Include copyable examples for an existing repository and a new project:
  - `仓库：D:\path\to\repo`
  - `新项目：snake-game`
- Mention that new HTML/web game requests should normally use the `新项目：snake-game` form.
- Keep the existing one-line resume parser unchanged so multi-line explanatory replies are not accidentally treated as resume directives.
- Update README and `journey/design.md` to record the blocked workspace guidance standard.

## Verification

- Extend `tests/test_pipeline_start.py` assertions for the blocked workspace reply.
- Add resume parser coverage for single-line repo, single-line new project, and multi-line non-resume replies.
- Run `uv run pytest tests/test_pipeline_start.py -q -p no:cacheprovider`.
- Run `uv run pytest tests/test_checkpoint.py tests/test_solution_design.py tests/test_pipeline_start.py -q -p no:cacheprovider`.

## Assumptions

- No schema or checkpoint state changes are needed.
- The bot should not infer or create a workspace without an explicit user reply in this slice.
