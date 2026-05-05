# Lark CLI Real Integration Plan

Date: 2026-05-03

## Goal

Install and lock the official `lark-cli` integration at version `1.0.14`, then provide a local doctor check for real Feishu/Lark document smoke tests.

## Implementation

- Install global `@larksuite/cli@1.0.14` and official AI Agent Skills.
- Add project-level npm metadata and lockfile with `@larksuite/cli = 1.0.14`.
- Add `devflow intake doctor` to check local config, CLI presence, locked version, and auth status availability.
- Document setup, credential requirements, and real document smoke testing.

## Verification

- Check `lark-cli --version` reports `1.0.14`.
- Run `devflow intake doctor`.
- Run `uv run python -m unittest discover -s tests -v`.
- If `config.json` has `lark.test_doc` and CLI auth is configured, run real `from-doc` smoke test.

## Assumptions

- `config.json` remains local and ignored.
- Real Feishu/Lark App ID, App Secret, and OAuth login may need user interaction outside automated tests.
