# DevFlow Engine Design Snapshot

Last updated: 2026-05-06 (Restored Chinese console messages after UTF-8 encoding fix)

## Working Rules

- **Use `uv` for Python**: prefer `uv pip install`, `uv run`, `uv venv` over pip/conda.
- **Use PowerShell**: all CLI operations use PowerShell syntax; avoid cmd.exe/Bash.
- **PowerShell Limitation**: PowerShell does not support `&&` syntax for chaining commands; use semicolon `;` or separate commands instead.
- **Use Standard Git Commit**: follow conventional commits format (`type(scope): subject`) with clear, descriptive messages; keep commits atomic and focused.
- **Clean Up Temporary Scripts**: delete any temporary scripts created for testing or validation purposes once verification is complete.

## Journey Memory

Use `journey/` as the shared project memory across agent sessions.

- Read `journey/design.md` first at the start of each session. It is the canonical snapshot of the project: current strategy, key design decisions, trade-offs, constraints, and scope.
- Use `journey/logs/` for chronological process notes, progress, experiments, and failed paths.
- Use `journey/research/` for research notes and background findings.
- Update `journey/design.md` whenever the effective understanding of the project changes. Do not leave important decisions or trade-offs only in logs.

For any new project, planning-focused request, or sufficiently complex task, start with a fresh plan and write it to `journey/plans/YYYY-MM-DD-{title}.md` before implementing. Treat files in `journey/plans/` as the canonical plans. As work progresses, record concise updates in `journey/logs/YYYY-MM-DD-{title}.md` using the same date and title convention. In chat, provide only a brief summary and the relevant file path(s).

## Current Focus

The current deliverable is a Python CLI and REST minimal DevFlow runtime. It includes six real nodes, `requirement-intake-agent`, `solution-design-agent`, `code-generation-agent`, `test-generation-agent`, `code-review-agent`, and `delivery-agent`, with a LangGraph-backed runner used for API-triggered runs and checkpoint continuation. `devflow start` remains the one-command bot-driven entrypoint that creates a minimal pipeline run for each incoming requirement message, asks for human approval after technical solution design, generates workspace-scoped code changes after approval, generates/runs tests, reviews the change, pauses on the second human checkpoint for code review confirmation, and then produces a final delivery package.

## Scope

- In scope: bounded reads from Feishu document URLs/tokens, specific IM messages, bounded bot event consumption, and continuous bot-driven startup through `lark-cli`.
- In scope: a stable `devflow.requirement.v1` JSON contract with progressive disclosure sections.
- In scope: a distilled Product Requirement Analyst prompt based on public PM skill patterns.
- In scope: a stable `devflow.solution_design.v1` JSON contract that combines structured requirements with bounded codebase context.
- In scope: a stable `devflow.code_generation.v1` JSON contract that records approved solution execution, tool calls, changed files, and git diff output.
- In scope: a stable `devflow.test_generation.v1` JSON contract that records test generation inputs, detected test stack, generated tests, command execution results, tool calls, and git diff output.
- In scope: a stable `devflow.code_review.v1` JSON contract that records review inputs, quality gate, findings, test summary, diff summary, repair recommendations, tool calls, and human-readable review status.
- In scope: a stable `devflow.checkpoint.v1` JSON contract for the first human review checkpoint after solution design and the second checkpoint after code review.
- In scope: a stable `devflow.delivery.v1` JSON contract that records approved delivery inputs, change summary, verification evidence, Git state, diff statistics, untracked text patches, and merge readiness.
- In scope: a minimal `devflow.pipeline_run.v1` run record with real `requirement_intake`, conditional `solution_design`, approval-gated `code_generation`, automatic `test_generation`, automatic `code_review`, and approval-gated `delivery`.
- In scope: a `devflow.pipeline_config.v1` JSON contract for built-in stage templates, stage ordering, dependencies, and built-in agent bindings.
- In scope: a LangGraph-backed graph runner that records `graph_state`, enforces `lifecycle_status`, and resumes approved checkpoints against the existing run directory.
- In scope: an AST-based semantic indexing system (`devflow.semantic`) that provides structured code understanding for DevFlow agents, including symbol extraction, reference tracking, call-chain queries, and inheritance hierarchy lookup.
- In scope: interactive API documentation via Swagger UI (`/docs`) and ReDoc (`/redoc`), served as CDN-backed HTML pages that reference the existing OpenAPI 3.0.3 JSON spec at `/api/v1/openapi.json`.
- Out of scope for this slice: full pipeline orchestration, web UI, REST API lifecycle management, and direct code generation.

## Key Decisions

- Use Python with `uv`; keep runtime dependencies low for a low-friction first demo.
- Use LangGraph as the orchestration framework for the pipeline runner while preserving the existing agent implementations and JSON artifact store.
- Treat `lark-cli` as an external integration boundary. The project shells out to it and validates/normalizes its JSON output.
- Store local runtime credentials in ignored `config.json`, with `config.example.json` as the committed schema template.
- Lock the intended `lark-cli` version in config to `1.0.23`.
- Lock official `@larksuite/cli` at `1.0.23` globally for real smoke tests and in `package-lock.json` for reproducible local setup.
- On Windows, prefer `lark-cli.cmd` from Python to avoid PowerShell execution policy blocking the `.ps1` shim.
- On Windows, use `shell=False` for all `subprocess.run()` / `subprocess.Popen()` calls that execute `lark-cli.cmd`. Using `shell=True` passes the command through `cmd.exe /c`, which has two critical defects: (1) `cmd.exe` strips leading/trailing quotes when the command line contains more than two quote characters, corrupting the executable path when `--content` passes JSON with embedded double quotes; (2) `cmd.exe /c` has an 8,191-character command line limit versus `CreateProcessW()`'s 32,768-character limit. With `shell=False`, `CreateProcessW()` automatically delegates `.cmd` files to `cmd.exe` without going through the `/c` quoting trap. The `LarkCliError` message includes the resolved executable path for diagnostics.
- For `lark-cli` 1.0.23 bot event intake, use `event consume im.message.receive_v1 --as bot`, passing `--max-events` and `--timeout` when bounded runs are requested.
- `lark-cli event consume` internally uses WebSocket long-connection (飞书长连接模式) to receive events. This means the project does NOT need a public IP, domain, or webhook callback URL — the `lark-cli` subprocess establishes a WebSocket full-duplex channel to `wss://open.feishu.cn` and streams events as NDJSON to stdout. This is the officially recommended approach per the 2026-05 Feishu open platform announcement. Constraints: 3-second event processing timeout (mitigated by immediate confirmation reply), cluster mode (no broadcast, single-client only), enterprise self-built apps only, max 50 connections per app.
- `devflow start` also uses `event consume im.message.receive_v1 --as bot`, with `--once` for demos/tests and no default timeout for continuous listening.
- `devflow start --force-subscribe` is removed; the runtime now follows the 1.0.23 event consume lifecycle instead of the old subscribe/force shape.
- Bot message input detection prefers Feishu document URLs/tokens, then `om_...` message ids, then inline natural-language requirement text.
- Each bot-triggered run is stored under `artifacts/runs/{run_id}/` with `run.json` and, on success, `requirement.json`.
- Each bot-triggered run also writes requirement-stage audit logs in the same run directory: `trace.jsonl`, plus `llm-request.json` and `llm-response.json` when the LLM analyzer is used.
- Solution design is LLM-only. `devflow design from-requirement` accepts `--repo` for an existing local folder or `--new-project` for a new folder under `workspace.root`.
- `devflow start` runs `solution_design` after successful LLM requirement intake when a workspace can be resolved from `仓库：...`, `新建项目：...`, or `workspace.default_repo`; otherwise the stage becomes `blocked`, writes `checkpoint.json`, and puts the exact blocked reason plus copyable one-line recovery formats (`仓库：D:\path\to\repo` or `新项目：snake-game`) in the first line of the bot reply because Feishu reply previews may hide later lines.
- Workspace resolution v1 supports only local existing paths and new local projects. Git URLs and uploaded archives are deferred.
- When `workspace.root` is configured, explicit repo paths and `workspace.default_repo` must both resolve inside that root; otherwise solution design blocks with the exact root-boundary reason.
- New project setup creates the directory under `workspace.root` and initializes Git; solution design itself remains read-only with respect to business code.
- Solution-stage audit files are written as `solution-llm-request.json` and `solution-llm-response.json`.
- Solution design normalization accepts loose-but-semantic LLM section shapes from real providers: string values for major sections are mapped into canonical nested fields, `file_path/change_type/description` are accepted as `change_plan` aliases, and `human_review.review_items` is accepted as a checklist alias. The prompt also includes an exact response skeleton so future model calls are guided toward the canonical object shape.
- Successful solution design writes both machine-readable `solution.json` and human-readable `solution.md`, then writes `checkpoint.json` with status `waiting_approval`.
- Code generation is implemented as a Python-native `devflow.code` package inspired by mature code-agent tool surfaces rather than vendoring a full Rust or Node runtime. The v1 tool surface includes `read_file`, `write_file`, `edit_file`, `glob_search`, `grep_search`, `semantic_search`, and a conservative `powershell` tool guarded by workspace and destructive-command checks.
- `devflow code generate` manually consumes a `solution.json` or a run id and writes `code-generation.json` plus a sibling `.diff` file.
- Test generation is implemented as a Python-native `devflow.test` package using the same bounded tool loop as code generation. It detects existing test stacks rather than vendoring external generators: Python uses pytest/unittest commands, JavaScript/TypeScript uses `npm.cmd test` when a test script exists, and Java uses Maven/Gradle commands.
- `devflow test generate` manually consumes a run id or explicit requirement/solution/code-generation artifacts and writes `test-generation.json` plus a sibling `.diff` file.
- Code review is implemented as a Python-native `devflow.review` package with read-only tools over the workspace. It reviews requirement alignment, correctness, security, test adequacy, maintainability, and operational risk, then writes `code-review.json` plus `code-review.md`.
- `devflow review generate` manually consumes a run id or explicit requirement/solution/code-generation/test-generation artifacts and writes `code-review.json` plus a sibling Markdown report.
- Delivery is implemented as a deterministic `devflow.delivery` package. It runs only after the `code_review` checkpoint is approved, writes `delivery.json`, `delivery.md`, and `delivery.diff`, captures Git branch/HEAD/status/tracked diff plus untracked text-file patches, and records advisory merge readiness without creating commits, pushes, or PRs.
- `devflow delivery generate` manually consumes a run id and regenerates the delivery package from the run artifacts and approved checkpoint.
- When a solution checkpoint is approved and the run has `solution_artifact`, the runtime immediately executes `code_generation`, `test_generation`, and `code_review`; older runs without a solution artifact keep the legacy continuation request.
- If code review finds blocking issues, the runtime injects the review findings into the next code-generation prompt and automatically retries `code_generation` → `test_generation` → `code_review` once. After that single repair attempt, it always stops on the code-review checkpoint for human decision.
- When a code-review checkpoint is approved, the runtime immediately executes `delivery` and marks the run as `delivered`. Rejecting the code-review checkpoint does not create delivery artifacts; it follows the existing repair/reject flow.
- The first checkpoint supports **two action channels** (v2):
  1. **Lark External Approval (primary)** — when `approval.enabled` is true, the pipeline auto-creates a third-party (external) approval definition via `POST /open-apis/approval/v4/external_approvals` if one does not already exist, then syncs an approval instance via `POST /open-apis/approval/v4/external_instances`. This does NOT require a pre-configured admin console template. The user receives the approval todo in the Feishu Approval app with "Approve" and "Reject" action buttons; rejection requires a comment. `devflow checkpoint poll` queries the external instance status and syncs results back to `checkpoint.json`.
  2. **Bot message replies (fallback)** — when approval is disabled or creation fails, the system falls back to the v1 card-based channel because `lark-cli` 1.0.23 exposes IM message events but not card button callback events. `Approve <run_id>` records approval and a continuation request; `Reject <run_id>` starts a two-turn rejection flow that captures the next reply as the reject reason and reruns `solution_design`.
  3. **Future: card callback via long-connection** — if `lark-cli` adds support for consuming `card.callback` events through the same WebSocket long-connection channel, the approval interaction can be upgraded from text-based commands to in-card button clicks, significantly improving UX. This is a deferred improvement, not a current blocker.
- The solution review checkpoint now enforces a **readiness gate** before approval. When the solution's `quality.ready_for_code_generation` is `false`, the checkpoint status becomes `waiting_approval_with_warnings`, the review card shows quality warnings with an orange header, and normal approval is blocked. Users can force approval with `Approve <run_id> --force` (or `强制通过` / `强制同意` / `override`), which records `approved_with_override` status along with `override_reason` and `quality_at_approval` snapshot for audit.
- `QualityGateError` is raised when code generation is attempted against a solution not marked ready. The pipeline catches this gracefully, sets the `code_generation` stage to `failed`, updates `run.json` status/lifecycle_status to `failed`, and continues processing subsequent events instead of crashing.
- `devflow checkpoint decide` records local checkpoint decisions, `devflow checkpoint resume` resumes a blocked run after local repo/new-project context is provided, and `devflow checkpoint poll` syncs Lark approval statuses for runs awaiting approval.
- On successful requirement analysis, `devflow start` creates a bot-owned PRD document with `docs +create --api-version v2 --as bot --doc-format markdown --content ...`, then replies to the triggering message with an interactive preview card using `im +messages-reply --msg-type interactive --content ... --as bot`.
- Analysis failures still use the simpler text reply path with `im +messages-reply --message-id ... --text ... --as bot`.
- PRD publishing is recorded separately from `requirement_intake`: if analysis succeeds but document creation or card reply fails, the stage remains `success` and `run.json.publication` records the publish error.
- If PRD document creation succeeds without returning a URL, the preview card must not emit an empty Markdown link; it shows a plain "created, link unavailable" status instead.
- If the success-path PRD card reply fails after analysis has completed, `devflow start` sends a text fallback reply so the user still receives a visible completion message and can inspect `run.json`.
- Interactive cards must use `lark_md`-safe formatting only. The `- ` unordered list syntax is not supported in `lark_md` text elements (it is only valid in dedicated `markdown` components); using it causes Lark API error `99992402` / "field validation failed". All card list items use `• ` (Unicode bullet) instead.
- If the solution review checkpoint card fails to publish, `publish_solution_review_checkpoint` records the error in `run_payload["reply_error"]` so that subsequent text replies can include a failure notice, and the resume/rerun text reply paths also catch `LarkCliError` to avoid crashing the pipeline.
- Use LLM analysis by default through OpenAI-compatible Chat Completions. Supported provider keys are `ark`, `bailian`, `deepseek`, `openai`, and `custom`.
- LLM calls expose a rich completion result internally so the pipeline can persist raw request/response payloads, provider token usage, usage source, and request duration while keeping API keys and Authorization headers out of audit files.
- Keep the deterministic local analyzer as explicit `--analyzer heuristic` offline mode.
- Use progressive disclosure: top-level JSON stays compact, while long source content is split into indexed sections.
- Keep JSON contract field names, schema versions, stage/status values, source types, and provider keys in English for downstream compatibility.
- Use Simplified Chinese for human-readable runtime output: prompts, generated artifact values, open questions, quality warnings, bot replies, CLI help/status lines, and actionable error text.
- Approval integration uses `lark-cli api` bare calls for:
  - `POST /open-apis/approval/v4/external_approvals` — create third-party approval definition (no admin console required)
  - `POST /open-apis/approval/v4/external_instances` — sync third-party approval instance with tasks and action configs
  - `GET /open-apis/approval/v4/external_instances/:id` — query third-party instance status
  - `POST /open-apis/approval/v4/instances` and `GET /open-apis/approval/v4/instances/:id` — legacy native approval (kept for backward compatibility)
  lark-cli 1.0.23 does not wrap these endpoints in its `approval` service. The `approval` service only exposes `instances.get`, `instances.cancel`, `instances.cc`, `instances.initiated`, `tasks.approve`, `tasks.reject`, `tasks.transfer`, `tasks.query`, and `tasks.remind`.
- Semantic indexing is implemented as `devflow.semantic` with AST-based code understanding. Python files use the built-in `ast` module (zero dependency); JavaScript/TypeScript files use `tree-sitter` with lazy import and graceful degradation when not installed. The index is stored as JSON files under `{workspace}/.devflow-index/` with `symbols.json`, `relations.json`, `file_meta.json`, and `summary.json`. Incremental updates use SHA256 hash-based change detection. The `semantic_search` tool supports five query types: symbol search, references, callers, hierarchy, and dependencies. `build_codebase_context` appends semantic summary, top-level symbols, and relation counts to its output. The feature is controlled by `SemanticConfig` in `config.json` and can be disabled.
- All `subprocess.run(text=True, ...)` calls must explicitly specify `encoding="utf-8"` and `errors="replace"` to avoid Windows GBK default codec failures. The `stdout`/`stderr` return values must be defensively checked for `None` before slicing or string operations, because a `UnicodeDecodeError` in the internal reader thread leaves them as `None`. This pattern is already followed in `delivery/agent.py` and `intake/lark_cli.py` and must be applied consistently to all new subprocess calls.
- Windows UTF-8 encoding is enforced at two levels: (1) `cross-env PYTHONUTF8=1` in the `npm run dev` script via `package.json`, ensuring Python's UTF-8 mode is active regardless of the system code page; (2) `$env:PYTHONUTF8 = "1"` in the PowerShell Profile for permanent effect. This eliminates the root cause of Chinese console output garbling on Windows (GBK/CP936 default). All previously English-only console messages (guidance, doctor output, poll status, semantic index, API server startup, error messages) have been restored to Simplified Chinese, consistent with the project's localization policy.
- Bot UX v2 improvements: When `default_chat_id` is not configured, `devflow start` prints console guidance in Simplified Chinese (previously English to avoid Windows GBK encoding issues, now safe with `PYTHONUTF8=1`); first-time bot interactions include a brief usage guide. When requirement analysis produces `open_questions` and `quality.ready_for_next_stage` is `false`, the pipeline pauses, writes a `waiting_clarification` checkpoint, and sends an orange "🔍 需求待澄清" card. Users can reply with answers or skip with `继续`/`skip`/`跳过`; the pipeline resumes with updated quality signals and continues to solution design. Solution design and code review artifacts are published as Feishu cloud documents with clickable links in review cards; file change/findings previews increased from 5 to 10 items. Checkpoint commands support run_id prefix matching with ambiguity detection. Approval confirmation replies include the operation type and full run_id. Stage failure messages include stage-specific recovery suggestions. LLM calls trigger "🤔 {stage}：正在思考…" notifications and 30-second timeout reminders when `progress_notifications_enabled` is true.
- Interactive API documentation is served via CDN-backed Swagger UI and ReDoc HTML pages. The `devflow.api` module defines `SWAGGER_UI_HTML` and `REDOC_HTML` as module-level string constants that load frontend resources from unpkg (swagger-ui-dist@5.20.1) and cdn.redoc.ly respectively. Both reference the existing `/api/v1/openapi.json` endpoint. Routes are `GET /docs` (Swagger UI) and `GET /redoc` (ReDoc). The OpenAPI spec self-describes these endpoints under the `Meta` tag. This approach adds zero Python dependencies and aligns with the project's stdlib-only principle. Offline support is deferred; if needed, CDN resources can be downloaded to `devflow/static/` as a fallback.

## Output Contract

Requirement artifacts use `schema_version = "devflow.requirement.v1"` and include metadata, source summary, normalized requirement, product analysis, acceptance criteria, implementation hints, open questions, sections, and quality signals.

Solution design artifacts use `schema_version = "devflow.solution_design.v1"` and include metadata, workspace, requirement summary, codebase context (with semantic_summary, semantic_symbols, semantic_relations_count), architecture analysis, proposed solution, change plan, API design, testing strategy, risks/assumptions, human review, quality, and prompt metadata.

Code generation artifacts use `schema_version = "devflow.code_generation.v1"` and include metadata, status, workspace, solution summary, changed files, Chinese summary/warnings, audited tool events, captured diff text, and prompt metadata.

Test generation artifacts use `schema_version = "devflow.test_generation.v1"` and include metadata, status, workspace, upstream input paths, detected stack, generated tests, test command results, Chinese summary/warnings, audited tool events, captured diff text, and prompt metadata.

Code review artifacts use `schema_version = "devflow.code_review.v1"` and include metadata, status, workspace, upstream input paths, review status, quality gate, findings, test summary, diff summary, repair recommendations, Chinese summary/warnings, audited tool events, and prompt metadata.

Delivery artifacts use `schema_version = "devflow.delivery.v1"` and include metadata, upstream inputs, approval record, change summary, verification evidence, Git state, and readiness.

Checkpoint artifacts use `schema_version = "devflow.checkpoint.v1"` and include run id, stage, status, attempt, reviewer, decision, reject reason, blocked reason, continuation flag, artifact history, and update timestamp.

Pipeline run records use `schema_version = "devflow.pipeline_run.v1"` and include trigger metadata, detected input, stage statuses, start/end timestamps, error details, artifact paths, publication status for PRD document/card delivery, `pipeline_config`, `graph_state`, `lifecycle_status`, and optional `provider_override`.

Pipeline config records use `schema_version = "devflow.pipeline_config.v1"` and include a template name plus validated built-in stage entries with `name`, `agent`, and `dependencies`.

Field names remain English and stable; human-readable field values are produced in Simplified Chinese.

Pipeline run records include an `audit` section pointing to the trace path and, when present, a compact LLM usage summary. Token usage is trusted only when returned by the provider; missing `usage` is recorded as missing rather than estimated.

## Trade-offs

- LLM failures fail the CLI directly in default mode, because requirement quality should not silently degrade once real model credentials are configured.
- The pipeline now executes solution design only when an LLM analyzer and resolvable workspace are available. Missing workspace context is a blocked checkpoint rather than a silent pending stage. Code generation runs only after solution approval and only inside the resolved workspace; test generation runs immediately after successful code generation and records failures on the `test_generation` stage while preserving code-generation artifacts. Code review runs after successful test generation and records a second human checkpoint; delivery runs after that checkpoint is approved.
- Test generation is LLM-driven and adapts to the detected test stack. For projects with standard frameworks (pytest, jest, maven), the agent can execute test commands and record pass/fail results. For projects without standard frameworks (e.g., pure HTML), the agent generates appropriate test artifacts (e.g., browser-based test pages) but cannot provide automated CI feedback. The `test_generation.diff` is empty for workspaces without `.git`, which is expected.
- Code review is LLM-driven but intentionally read-only. Automatic repair is limited to one retry to demonstrate regression while avoiding unbounded loops.
- Delivery v1 is package-only. It does not create branches, commits, pushes, or PRs; it records the evidence and readiness needed for a human to merge or decide the next Git action.
- `devflow start` is a useful long-running CLI process, but production-grade daemon supervision and REST lifecycle controls are still deferred.
- Semantic indexing v1 uses heuristic call-target resolution (no type system), so cross-file call accuracy is approximately 70-80%. Tree-sitter is optional; when not installed, JS/TS files are skipped with UNAVAILABLE status. The index is stored as flat JSON rather than a database, which is sufficient for workspaces under ~1000 files. Cross-file symbol resolution and type-aware call analysis are deferred to v2.
