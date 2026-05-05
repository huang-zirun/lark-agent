# Fix Welcome Message Truncation Log

## Context

Startup welcome delivery currently builds a complete multiline guide, but users only see the first line: `🤖 DevFlow 已就绪`.

## Root Cause

`send_bot_text()` passes the multiline body through `lark-cli im +messages-send --text`. On Windows the project runs `lark-cli.cmd` through `shell=True`; raw newline characters remain inside the command line and can split or truncate the effective argument. Sending the same body as JSON content escapes newlines as `\n`, which keeps the payload intact.

## Planned Fix

- Route `send_bot_text()` through `--msg-type text --content <json>`.
- Use a higher-entropy welcome idempotency key for rapid restarts.
- Refresh welcome-message tests so they cover the actual text helper.

## Implementation

- Updated `send_bot_text()` to JSON-wrap text content and avoid raw newline arguments.
- Updated `_send_welcome_message()` to use `time.time_ns()` in the welcome idempotency key.
- Added a regression test for multiline text delivery and refreshed stale welcome tests to mock `send_bot_text()`.
- Updated `journey/design.md` with the multiline IM text constraint.
- While running the full suite, refreshed three stale doctor-output assertions in `tests/test_config.py` to match the existing English CLI output.

## Verification

- Red test observed: `uv run python -m pytest tests/test_welcome_message.py::SendBotTextTests::test_multiline_text_sent_as_json_content -q` failed because `--text` was still present.
- Green focused test observed: the same command passed after the helper change.
- Welcome suite observed: `uv run python -m pytest tests/test_welcome_message.py -q` passed with 16 tests.
- Startup loop regression observed: `uv run python -m pytest tests/test_pipeline_start.py::PipelineStartTests::test_cli_start_once_processes_mocked_event -q` passed.
- Initial full-suite run hit a local temp-directory permission error at `C:\Users\huang\AppData\Local\Temp\pytest-of-huang`; rerunning with workspace basetemp avoided the environment issue.
- Full suite observed: `uv run python -m pytest -q --basetemp .test-tmp\pytest-basetemp` passed with 340 tests, 2 skipped, and 2 subtests.
