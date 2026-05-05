# Requirement Intake Agent Enhancement Log

Date: 2026-05-06

## Summary

Enhanced `ProductRequirementAnalyst` by borrowing design patterns from `docs/SKILL.md` (a Claude Code PM skill). The agent remains a single-shot analysis node — no Clarify mode or multi-round interaction was introduced.

## Changes

### prompt.py — System Prompt

Added 5 new sections to `PRODUCT_REQUIREMENT_ANALYST_PROMPT`:
- 6-step analysis workflow (parse → infer → limit clarification → prioritize stories → EARS → self-check)
- 7-dimension structured scanning framework (functional scope, domain model, UX flow, non-functional, external deps, edge cases, vague placeholders)
- Vague expression detection rules (4 categories: unquantified performance, undefined scope, subjective evaluation, undefined pronouns)
- EARS syntax pattern examples (5 patterns: unconditional, event-driven, negative, state-driven, optional)
- Quality self-check instructions (3 dimensions: content quality, requirement completeness, functional readiness)

### analyzer.py — Core Logic

- `build_llm_user_prompt()`: Updated structure requirements for `user_stories` (structured objects), `open_questions` (with suggested_answer/reasoning), `quality.dimensions`
- `normalize_llm_analysis()`: Added `_user_stories_list()` parser for structured user stories; backward-compatible `user_scenarios` auto-generated from stories; `quality.dimensions` parsing
- `build_artifact_payload()`: Added `input_history` field with verbatim raw input
- `build_open_questions()`: Added `content` parameter, integrated `_detect_vague_expressions()` with 3 vague pattern categories
- `build_quality()`: Added `content` parameter, `dimensions` sub-object, vague expression count affecting ambiguity_score and warnings
- `build_quality_warnings()`: Added `vague_count` parameter
- New `_VAGUE_PATTERNS` constant and `_detect_vague_expressions()` function
- New `_user_stories_list()` function with full structured parsing

### prd.py — Rendering

- New `_append_input_history()`: Renders input history with blockquote format
- New `_append_user_stories()`: Renders user stories with priority, independent test, Given/When/Then scenarios
- New `_append_open_questions()`: Renders open questions with suggested_answer and reasoning
- `_append_quality()`: Added dimensions rendering
- New `_preview_open_questions()`: Preview card support for suggested answers
- `render_prd_markdown()`: Integrated new sections (input_history before background, user_stories before user_scenarios, open_questions replaces flat list)

## Test Results

277 passed, 2 skipped, 1 error (unrelated Windows temp dir PermissionError)

## Design Decisions

- Single-shot only: No Clarify mode. The agent accepts raw input and produces one structured output. Clarification questions are embedded in `open_questions` with `suggested_answer` and `reasoning` for downstream use.
- Backward compatibility: `user_scenarios` string array preserved alongside `user_stories` structured objects. Downstream agents that read `user_scenarios` continue to work.
- Incremental schema: New fields (`input_history`, `user_stories`, `quality.dimensions`, `open_questions.suggested_answer/reasoning`) are additive. Missing fields default gracefully.
- Vague detection in heuristic mode: Uses regex patterns for 3 categories. LLM mode relies on the enhanced prompt instructions instead.
