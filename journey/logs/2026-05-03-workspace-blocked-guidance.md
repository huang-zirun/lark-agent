# Workspace Blocked Guidance Log

Date: 2026-05-03

## Progress

- Started from the approved implementation plan.
- Confirmed existing runtime already blocks missing workspace context and can resume from a one-line `仓库：...` or `新项目：...` reply.
- Added failing coverage for the blocked bot reply and one-line workspace resume recognition.
- Updated the blocked workspace reply to explain the missing context, show copyable one-line examples, and clarify that DevFlow will continue with solution design and the review card after the reply.
- Documented the guidance standard in README and the canonical design snapshot.
- Verified with `uv run pytest tests/test_pipeline_start.py -q -p no:cacheprovider`: 16 passed.
- Verified with `uv run pytest tests/test_checkpoint.py tests/test_solution_design.py tests/test_pipeline_start.py -q -p no:cacheprovider`: 23 passed.
- Attempted full `uv run pytest -q -p no:cacheprovider`; sandboxed runs failed on Python `tempfile.TemporaryDirectory` write/cleanup permission errors, and escalation review timed out twice.
- Follow-up investigation found the latest real run was blocked by config mismatch: `workspace.default_repo = D:\lark` was outside `workspace.root = D:\lark\workspaces`, and the Feishu reply preview only exposed the first line. Updated the blocked reply so the first line contains the exact blocked reason and the one-line recovery formats.
