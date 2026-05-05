# Fix Welcome Message Truncation Plan

## Summary

`devflow start` sends a multiline welcome text on startup, but Windows command invocation can pass only the first line reliably when the text is sent through `lark-cli im +messages-send --text`. The fix is to keep the public Python helper API unchanged while sending text as JSON content so newline characters are escaped before crossing the shell boundary.

## Key Changes

- Add a regression test proving `send_bot_text()` sends multiline text through `--msg-type text --content {"text": ...}` instead of `--text`.
- Update `_send_welcome_message()` to keep the plaintext welcome body and use a nanosecond idempotency key so quick restarts do not collide.
- Update stale welcome tests to mock the current text-send path and assert the full guide content is sent.
- Update design memory to record that multiline IM text should be sent through JSON content.

## Test Plan

- `uv run python -m pytest tests/test_welcome_message.py::SendBotTextTests::test_multiline_text_sent_as_json_content -q`
- `uv run python -m pytest tests/test_welcome_message.py -q`
- `uv run python -m pytest tests/test_pipeline_start.py::PipelineStartTests::test_cli_start_once_processes_mocked_event -q`
- `uv run python -m pytest -q`

## Assumptions

- Keep the startup welcome as plaintext rather than returning to an interactive card.
- Leave `--once` behavior unchanged; one-event demo mode is not the truncation root cause.
