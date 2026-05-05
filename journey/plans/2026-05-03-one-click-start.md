# One-Click Start Minimal Pipeline Plan

Date: 2026-05-03

## Goal

Add `devflow start` as the first one-command system entrypoint. It should continuously listen for Feishu/Lark bot messages, recognize the requirement source from each message, run the existing requirement intake node, persist a minimal pipeline run, and reply to the triggering message with the result.

## Implementation

- Keep `lark-cli` as the integration boundary and continue using `event +subscribe --as bot --event-types im.message.receive_v1` for the locked 1.0.14 CLI shape.
- Add a small pipeline module that owns input detection, run ids, stage records, run JSON, success/failure reply text, and single-event processing.
- Add `devflow start` with `--once`, `--timeout`, `--out-dir`, `--model`, and `--analyzer`.
- Detect Feishu document URLs/tokens first, then `om_...` message IDs, then treat the bot message body as inline requirement text.
- Send bot replies with `im +messages-reply --message-id ... --text ... --as bot` and an idempotency key.

## Verification

- Unit tests for input detection, run persistence, reply text, and failure records.
- CLI tests with mocked event intake and reply sending.
- Regression test the existing intake commands.
