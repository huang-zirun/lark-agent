# Config JSON Credentials Plan

Date: 2026-05-03

## Goal

Store local LLM and Lark credentials in an ignored `config.json` file, with a safe committed template and a small loader for CLI workflows.

## Implementation

- Ignore `config.json` and `key.md` so local secrets are not committed.
- Add `config.example.json` with empty credential fields and locked `lark.cli_version = "1.0.14"`.
- Add a standard-library config loader that reads `config.json`, validates requested fields, and never includes secret values in errors.
- Let `devflow intake from-doc` use `lark.test_doc` from `config.json` when `--doc` is omitted.
- Document the local setup flow in README.

## Verification

- Unit tests for missing config, invalid JSON, missing required fields, valid config loading, secret-safe errors, and CLI config fallback.
- Run `uv run python -m unittest discover -s tests -v`.

## Assumptions

- `config.json` is for local runtime only and should remain ignored.
- Existing `key.md` contains the current LLM API key and will be migrated locally without printing the value.
