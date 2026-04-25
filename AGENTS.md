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

## Design Principles

- **Fast Fail**: Pre-validate before model calls or code changes; fail immediately with clear errors.
- **AI-Friendly**: Structured, low-ambiguity inputs/outputs; explicit schemas and verifiable artifacts.
- **First Principles**: System = verifiable state transitions + reusable artifacts + constrained side effects.
- **TDD-First**: Validate state machines and contracts before implementation; write failing tests first.
- **Reject Ad-hoc Patches**: Fix templates/schemas/state machines, not just prompts or branches.
- **KISS**: Modular monolith, explicit contracts, minimal state. No microservices unless necessary.

## Journey Memory

- `journey/design.md`: canonical project snapshot.
- `journey/logs/`: chronological progress and experiments.
- `journey/research/`: research notes.
- `journey/plans/YYYY-MM-DD-{title}.md`: canonical plans for new tasks.
- `journey/logs/YYYY-MM-DD-{title}.md`: progress updates.
