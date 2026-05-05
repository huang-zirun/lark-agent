# lark-cli 1.0.23 Migration Plan

## Goal

Pin DevFlow to `@larksuite/cli` / `lark-cli` `1.0.23` and migrate all runtime calls away from the 1.0.14 command surface.

## Implementation

- Update version locks in Python config, JSON config template, npm metadata, README, and design memory.
- Replace `docs +fetch` with the v2 Markdown fetch form: `docs +fetch --api-version v2 --doc <doc> --doc-format markdown --format json`.
- Replace PRD creation with the v2 Markdown create form: `docs +create --api-version v2 --as bot --doc-format markdown --content <markdown>`.
- Replace `event +subscribe` with bounded `event consume im.message.receive_v1 --max-events <N> --timeout <Ns> --as bot`.
- Remove `devflow start --force-subscribe` and all `force_subscribe` plumbing.

## Verification

- Run focused failing tests after updating expectations.
- Run `uv run pytest tests -q -p no:cacheprovider`.
- Run npm install/version checks for local and global `@larksuite/cli@1.0.23`.

## Assumptions

- No backwards compatibility is required for `event +subscribe` or `--force-subscribe`.
- Existing Markdown PRD rendering remains the document source.
