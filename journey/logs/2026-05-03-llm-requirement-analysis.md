# LLM Requirement Analysis Log

## 2026-05-03

- Started implementing multi-provider LLM requirement analysis.
- Confirmed current artifact generation is centralized in `devflow.intake.analyzer.build_requirement_artifact`.
- Confirmed `config.json` has `llm.provider=ark` and an API key, but no `llm.model` or `llm.base_url` yet.
- Extended config schema with LLM model, base URL, temperature, max tokens, and timeout.
- Added a standard-library OpenAI-compatible Chat Completions client for `ark`, `bailian`, `deepseek`, `openai`, and `custom`.
- Added LLM analyzer path while preserving explicit `--analyzer heuristic`.
- Made CLI intake default to `--analyzer llm`; `--analyzer heuristic` remains available for offline checks.
- Extended `devflow intake doctor` with LLM config validation and optional `--check-llm`.
- Verified `uv run python -m unittest discover -s tests -v` passes.
- Verified heuristic mode still writes an artifact.
- Current real LLM blocker: local `config.json` is missing `llm.model`.
- Ark returned HTTP 400 when `response_format={"type":"json_object"}` was forced; changed JSON response_format to opt-in with `llm.response_format_json=false` by default.
- Increased default LLM timeout to 120 seconds and set local runtime timeout to 180 seconds for the real Ark smoke test.
- Verified `devflow intake doctor --check-llm` passes against Ark.
- Real LLM smoke test succeeded and wrote `artifacts\requirements\real-lark-doc-llm.json` with `metadata.analyzer=llm`.
