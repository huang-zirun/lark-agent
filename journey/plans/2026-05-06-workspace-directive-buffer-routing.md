# Workspace Directive Buffer Routing

## Background

Latest experiment data shows the run triggered by the user reply `新项目：snake-game` did not resume the previous blocked solution-design run. The newest run stored the detected input as:

```text
我想要制作一个贪吃蛇小游戏，夏天主题
新项目：snake-game
```

It then started a new `requirement_intake` LLM call and failed after the 120 second timeout. The previous run was already `blocked` at `solution_design` with `checkpoint.json`, waiting for workspace context.

## Root-Cause Hypothesis

`MessageBuffer` treats workspace recovery directives as normal text. When a user sends a requirement and quickly replies `新项目：snake-game`, the 5 second merge window combines the recovery directive into the previous requirement event. After merging, the first non-empty line is no longer a workspace directive, so `find_blocked_workspace_run()` does not route it to `resume_blocked_solution_design()`. DevFlow creates a new run and repeats requirement analysis.

This is a routing-boundary bug, not a solution-design or LLM prompt issue.

## Plan

1. Add a regression test showing that `MessageBuffer` must flush a buffered requirement when the next event is a workspace directive.
2. Treat first-line workspace directives as control events in `MessageBuffer`, using the existing `parse_workspace_directive()` parser rather than duplicating command syntax.
3. Run the focused tests for message buffering and pipeline workspace resume behavior.
4. Record the fix in `journey/logs/2026-05-06-workspace-directive-buffer-routing.md` and update `journey/design.md` if the effective design changes.

## Success Criteria

- A quick `新项目：snake-game` event is emitted as its own event, not merged into the preceding requirement.
- Existing command-buffer behavior remains intact.
- Existing workspace-resume semantics remain first-line based.
- Focused tests pass with `uv run`.
