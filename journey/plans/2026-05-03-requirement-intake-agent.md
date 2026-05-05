# Requirement Intake Agent Plan

Date: 2026-05-03

## Goal

Build the first DevFlow agent as a Python CLI that reads requirements from Feishu/Lark documents, IM messages, or bounded bot events and emits a downstream-agent-friendly JSON artifact.

## Implementation

- Create a `src/devflow` Python package with a `devflow` console script.
- Add `devflow intake from-doc`, `from-message`, and `listen-bot` commands.
- Wrap `lark-cli` calls behind a small adapter so tests can replace command execution.
- Normalize all input shapes into a `RequirementSource`.
- Analyze the source with a Product Requirement Analyst prompt and deterministic extraction rules.
- Emit `devflow.requirement.v1` JSON with compact top-level fields and chunked `sections`.

## JSON Contract

The artifact includes:

- `metadata`: source type, source id, generated timestamp, agent version, model, lark identity.
- `source`: source reference, safe summary, raw length, attachments, embedded resources.
- `normalized_requirement`: title, background, users, problem, goals, non-goals, scope.
- `product_analysis`: scenarios, business value, evidence, assumptions, risks, dependencies.
- `acceptance_criteria`: testable criteria in Gherkin-like wording when possible.
- `implementation_hints`: neutral handoff notes for a future solution-design agent.
- `open_questions`: missing information and product-manager follow-ups.
- `sections`: progressive-disclosure index over source chunks.
- `quality`: completeness, ambiguity, and readiness signals.

## Verification

- Unit tests for source normalization, schema generation, and content chunking.
- CLI tests with mocked `lark-cli` output for document, message, and event modes.
- Error-path tests for missing CLI, failed command, invalid JSON, and empty source content.

## Assumptions

- `lark-cli` may not be installed locally yet, so implementation must fail with actionable guidance.
- Runtime model is `heuristic-local-v1` until model provider configuration is added.
- The first node should be reusable by the later API/Pipeline engine without rewriting the core logic.
