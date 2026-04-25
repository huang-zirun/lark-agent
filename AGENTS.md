# Project Instructions for Agents

## Project Snapshot

- Entry for Feishu AI Campus Challenge, track: `AI Product Innovation`, topic 3: `DevFlow Engine`.
- Confirmed scope: core AI-driven requirement delivery engine per `function.md`.
- `docs/基于 AI 驱动的需求交付流程引擎（公开版）.md` is background material only.
- Repository is early-stage; verify existence of implementations before assuming.

## Source of Truth

- Read `journey/design.md` at session start for architecture, constraints, and terminology.
- Use `function.md` to verify boundaries and acceptance criteria.
- Update `journey/design.md` when project understanding changes.

## Current Repo Reality

- Do not assume `Vite+`, `package.json`, FastAPI, React, Docker Compose, or test commands exist.
- Verify all commands, paths, and tools against the repository before use.
- Treat stack in `journey/design.md` as planned, not implemented.

## Working Rules

- Prioritize competition MVP and current design baseline over speculation.
- Windows-first: respect PowerShell, UTF-8, CRLF, Chinese/spaced paths, and local Git constraints.
- Prefer updating design/plan/schema over ad-hoc patches.
- Ground in repo state before proposing changes for design-heavy tasks.
- **Use `uv` for Python**: prefer `uv pip install`, `uv run`, `uv venv` over pip/conda.
- **Use PowerShell**: all CLI operations use PowerShell syntax; avoid cmd.exe/Bash.
- **PowerShell Limitation**: PowerShell does not support `&&` syntax for chaining commands; use semicolon `;` or separate commands instead.
- **Use Standard Git Commit**: follow conventional commits format (`type(scope): subject`) with clear, descriptive messages; keep commits atomic and focused.

## Design Principles

- **Fast Fail**: Pre-validate before model calls or code changes; fail immediately with clear errors.
- **AI-Friendly**: Structured, low-ambiguity inputs/outputs; explicit schemas and verifiable artifacts.
- **First Principles**: System = verifiable state transitions + reusable artifacts + constrained side effects.
- **TDD-First**: Validate state machines and contracts before implementation; write failing tests first.
- **Reject Ad-hoc Patches**: Fix templates/schemas/state machines, not just prompts or branches.
- **KISS**: Modular monolith, explicit contracts, minimal state. No microservices unless necessary.

## Journey memory

Use `journey/` as the shared project memory across agent sessions.

- Read `journey/design.md` first at the start of each session. It is the canonical snapshot of the project: current strategy, key design decisions, trade-offs, constraints, and scope.
- Use `journey/logs/` for chronological process notes, progress, experiments, and failed paths.
- Use `journey/research/` for research notes and background findings.
- Update `journey/design.md` whenever the effective understanding of the project changes. Do not leave important decisions or trade-offs only in logs.

For any new project, planning-focused request, or sufficiently complex task, start with a fresh plan and write it to `journey/plans/YYYY-MM-DD-{title}.md` before implementing. Treat files in `journey/plans/` as the canonical plans. As work progresses, record concise updates in `journey/logs/YYYY-MM-DD-{title}.md` using the same date and title convention. In chat, provide only a brief summary and the relevant file path(s).
