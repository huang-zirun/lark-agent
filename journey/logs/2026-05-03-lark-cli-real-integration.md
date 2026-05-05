# Lark CLI Real Integration Log

## 2026-05-03

- Confirmed GitHub Releases still mark `v1.0.14` as the latest official `larksuite/cli` release.
- Installed global `@larksuite/cli@1.0.14`.
- Installed official larksuite CLI AI Agent Skills with `npx.cmd skills add larksuite/cli -y -g`.
- Added project `package.json` and `package-lock.json` with `@larksuite/cli` pinned to `1.0.14`.
- Found PowerShell direct `lark-cli` resolves to a blocked `.ps1` shim; updated Python integration to prefer `lark-cli.cmd` on Windows.
- Added `devflow intake doctor` for config, version, and auth readiness checks.
- Verified `lark-cli.cmd --version` and `npm.cmd run lark:version` both report `1.0.14`.
- Verified unit tests with `uv run python -m unittest discover -s tests -v`.
- `devflow intake doctor --skip-auth` now reaches config validation and reports the next blocker: `lark.app_id` is not filled in local `config.json`.
- After local `config.json` was filled, `devflow intake doctor` passed.
- First real `from-doc` attempt reached `lark-cli` but failed because v1.0.14 no longer supports old `docs +fetch` flags `--api-version` and `--doc-format`; updated the adapter to use the current `docs +fetch --doc ... --format json` contract.
- Confirmed the real v1.0.14 response shape uses `data.markdown`, `data.doc_id`, and `data.title`; updated normalization and added a regression test for that shape.
- Real smoke test succeeded and wrote `artifacts\requirements\real-lark-doc.json` with `schema_version=devflow.requirement.v1` and `source_type=lark_doc`.
- User hit `unknown flag: --as` when `listen-bot` called the unsupported `event consume ... --as bot --max-events ... --timeout ...` shape. Real v1.0.14 exposes `event +subscribe` instead.
- Updated bot event intake to call `event +subscribe --as bot --event-types im.message.receive_v1`, stream NDJSON from stdout, and enforce `max_events` / timeout in Python.
- Real short-timeout smoke test now reaches the event WebSocket path; with no incoming message it exits cleanly as "No bot events were received" instead of a CLI flag error.
