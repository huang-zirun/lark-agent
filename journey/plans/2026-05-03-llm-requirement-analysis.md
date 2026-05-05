# LLM Requirement Analysis Plan

Date: 2026-05-03

## Goal

Make requirement intake use a real LLM by default while preserving the existing `devflow.requirement.v1` artifact contract and explicit offline heuristic mode.

## Implementation

- Extend local `config.json` schema with OpenAI-compatible LLM settings.
- Support `ark`, `bailian`, `deepseek`, `openai`, and `custom` providers through a standard-library HTTP client.
- Add an LLM analyzer that asks for only the model-owned artifact fields and lets code keep metadata, source, sections, and prompt fields stable.
- Make CLI intake commands use LLM by default and add `--analyzer heuristic|llm`.
- Extend doctor with LLM config checks and an optional live LLM probe.

## Verification

- Unit tests for provider resolution, request construction, error handling, JSON validation, CLI analyzer selection, and doctor checks.
- Run `uv run python -m unittest discover -s tests -v`.
- If `config.json` has `llm.model`, run `uv run devflow intake doctor --check-llm`.

## Assumptions

- Providers are accessed through OpenAI-compatible Chat Completions in this slice.
- LLM failures should fail the CLI instead of falling back silently.
