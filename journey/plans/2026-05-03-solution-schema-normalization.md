# Solution Schema Normalization Fix

Date: 2026-05-03

## Problem

`devflow start` can block after solution design with `LLM 方案响应字段必须是对象：architecture_analysis。` A real audited response returned valid JSON, but several solution-design sections were strings instead of the nested objects required by `devflow.solution_design.v1`.

## Root Cause

The solution-design prompt lists required top-level fields but does not show the exact nested object shape. The normalizer is strict at the top-level section boundary, so provider responses that are semantically useful but structurally loose fail before they can be converted into the stable artifact contract.

## Plan

1. Add a regression test using the observed loose response shape: string sections, `change_plan.file_path/change_type/description`, `human_review.review_items`, and quality metadata without all canonical keys.
2. Update normalization to coerce semantically equivalent loose section shapes into the stable `devflow.solution_design.v1` object structure while preserving strict JSON parsing and required top-level fields.
3. Strengthen the prompt by embedding the exact response skeleton so future LLM calls are less likely to drift.
4. Run focused tests, then the full test suite.
5. Update `journey/design.md` and the matching log with the decision and verification result.

## Success Criteria

- The new regression test fails before the implementation change and passes afterward.
- Existing solution/pipeline tests continue to pass.
- Full `uv run pytest` passes.
- The project memory records that the solution design boundary now tolerates loose-but-semantic LLM section shapes.
