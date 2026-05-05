# PRD Card Publish Plan

## Summary

Add a publishing step to `devflow start` after requirement analysis succeeds. The pipeline keeps `requirement.json` as the machine-readable artifact, creates a bot-owned Feishu PRD document from the requirement artifact, and replies to the original bot-triggering message with an interactive preview card.

## Key Changes

- Render `devflow.requirement.v1` into a deterministic Markdown PRD without a second LLM call.
- Add Lark adapter functions for `docs +create --as bot --title ... --markdown ...` and `im +messages-reply --as bot --msg-type interactive --content ...`.
- Record publication details in `run.json`, including document URL/id, card reply status, and publication errors.
- Preserve `requirement_intake` success when analysis succeeds but PRD creation or card reply fails.
- Keep the existing failure-path text reply for analysis failures.

## Test Plan

- Unit test Markdown PRD rendering with complete and sparse requirement artifacts.
- Unit test Lark command construction for PRD creation and interactive card reply.
- Unit test pipeline publication success and publication failure semantics.
- Run focused pipeline/publication tests, then the full test suite.

## Assumptions

- PRD documents are created with bot identity.
- The card replies to the original message id from the bot event.
- The installed `lark-cli` shape is 1.0.14 and does not use `--api-version v2`.
