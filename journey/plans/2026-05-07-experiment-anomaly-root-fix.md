# Experiment Anomaly Root-Fix Implementation Plan

> **For agentic workers:** Implement with TDD. Fix root causes from `journey/logs/2026-05-07-experiment-anomaly-analysis.md`; do not add ad-hoc artifact rewrites for the analyzed historical run.

**Goal:** Future experiment runs expose truthful lifecycle state, publication state, change evidence, test evidence, branch metadata, and approval fallback behavior.

**Architecture:** Centralize run lifecycle synchronization in the pipeline layer, centralize workspace change evidence in code tools, and add deterministic validation around test artifacts. Preserve existing artifact fields for compatibility while adding structured fields for new evidence.

**Tech Stack:** Python stdlib, `uv`, pytest, existing DevFlow CLI/pipeline/test/review packages.

---

## Tasks

- [x] Add failing regression tests for waiting/checkpoint lifecycle, blocked-workspace resume cleanup, delivery terminal state, requirement publication recording, workspace-change evidence, branch metadata, plain HTML/JS stack detection, invalid copied tests, and compact tool-result context.
- [x] Implement lifecycle synchronization helpers and apply them after blocked checkpoints, waiting approvals, graph continuations, and delivery.
- [x] Normalize publication recording so `artifact_publications.requirement_intake` is populated and `document_id` without URL is treated as published-without-link.
- [x] Replace tracked-only git diff capture with structured workspace change evidence that includes untracked text files and excludes runtime directories.
- [x] Record actual Git branch metadata for new/existing workspaces, initializing new projects on `main` when supported.
- [x] Add test-validity evidence and make code review block tests that only duplicate production logic.
- [x] Compact code/test/review agent tool-result history and load reference docs once per run.
- [x] Add external approval capability preflight/cache so missing approval scopes fall back to cards without repeated external approval attempts.
- [x] Run focused verification and update `journey/design.md` plus the matching log.
