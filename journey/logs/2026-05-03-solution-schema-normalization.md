# Solution Schema Normalization Fix Log

## 2026-05-03

- Investigated blocked run `20260503T095354Z-om_x100b5045fded5ca8b279ff5c404d122-fa8cd8f0`.
- Found `solution-llm-response.json` contains valid JSON where `architecture_analysis`, `proposed_solution`, `api_design`, and `testing_strategy` are strings, while the runtime expects objects.
- Identified the root cause as a prompt/schema-boundary mismatch: required field names were specified, but the nested field shape was not explicit enough for all providers.
- Added a regression test for the observed loose provider shape, watched it fail on `LLM 方案响应字段必须是对象：architecture_analysis。`, then updated solution normalization to coerce those loose sections into the canonical contract.
- Strengthened the solution-design prompt with an exact `devflow.solution_design.v1` response skeleton.
- Verification:
  - `.venv\Scripts\python.exe -m pytest tests/test_solution_design.py::SolutionDesignTests::test_normalizes_loose_llm_solution_sections_from_provider_response -q -p no:cacheprovider`: passed.
  - `.venv\Scripts\python.exe -m pytest tests/test_solution_design.py tests/test_pipeline_start.py tests/test_checkpoint.py -q -p no:cacheprovider`: 25 passed.
  - Parsed the original `solution-llm-response.json` from the blocked run through the updated normalizer; it now yields `change_plan[0].path = index.html`, `quality.risk_level = low`, and `human_review.status = pending`.
  - `.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider`: 68 passed, 9 failed because sandboxed Python could not write files inside `tempfile.TemporaryDirectory()` paths. Retrying with `TMP/TEMP=D:\lark\.test-tmp` hit the same permission boundary.
