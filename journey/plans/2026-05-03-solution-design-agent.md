# Solution Design Agent Plan

Date: 2026-05-03

## Goal

Build the second DevFlow node, `solution-design-agent`, which consumes a `devflow.requirement.v1` artifact plus target workspace context and emits a `devflow.solution_design.v1` technical design JSON artifact.

## Implementation

- Add a workspace contract with v1 support for `existing_path` and `new_project`.
- Extend configuration with `workspace.root` and optional `workspace.default_repo`.
- Add a `devflow.solution` package for requirement validation, workspace resolution, codebase context scanning, LLM prompt construction, JSON normalization, and artifact writing.
- Add `devflow design from-requirement` for manual execution.
- Extend `devflow start` so successful requirement intake continues into `solution_design` and writes `solution.json` in the same run directory.
- Keep solution design LLM-only. Tests use mocked LLM responses; no heuristic design mode is added.

## JSON Contract

The solution artifact uses `schema_version = "devflow.solution_design.v1"` and includes metadata, workspace, requirement summary, codebase context, architecture analysis, proposed solution, change plan, API design, testing strategy, risks/assumptions, human review, quality, and prompt metadata.

## Verification

- Workspace tests for bot text parsing, new project path resolution, root safety, and context exclusions.
- Solution tests for mocked LLM success, malformed LLM responses, prompt contents, and artifact contract fields.
- Pipeline tests for `devflow start --once` producing `solution.json`, stage success, and trace events.
- Full regression with `uv run python -m unittest discover -s tests -v`.

## Assumptions

- Feishu bot messages can only pass paths/project names that are meaningful to the machine running DevFlow.
- Solution design reads repository files but does not write business code.
- New project setup creates the directory and initializes Git only; code generation remains a later stage.
