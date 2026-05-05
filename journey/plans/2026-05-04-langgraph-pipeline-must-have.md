# LangGraph Pipeline Must-have Implementation Plan

Date: 2026-05-04

## Goal

Replace the hardcoded pipeline continuation path with a LangGraph-backed orchestration core while preserving the existing JSON artifact store, `http.server` API surface, and six built-in agent implementations.

## Decisions

- Use LangGraph as the canonical execution wrapper around existing stage functions.
- Keep `artifacts/runs/{run_id}` as the durable state store.
- Keep `http.server` and existing REST paths.
- Support configurable built-in stage templates, not arbitrary plugin loading.
- Apply LLM provider override at run scope and persist it in `run.json`.
- Enforce pause/terminate at trigger and checkpoint boundaries.

## Tasks

1. Add tests for pipeline template validation and graph runner behavior.
2. Add API regression tests proving trigger executes the same run id and checkpoint actions respect lifecycle status.
3. Add a pipeline config module with built-in stage bindings, dependency validation, and cycle detection.
4. Add a LangGraph runner module that calls existing stage functions and records graph state.
5. Refactor API trigger/checkpoint and CLI checkpoint paths to use the runner.
6. Add dependency and documentation updates.
7. Run targeted tests and record verification notes.

