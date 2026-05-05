# Bot PRD Card Fallback Log

## 2026-05-03

- Investigated run `20260503T035705Z-om_x100b505837d754a8b34443c519d74b7-581d4da2`.
- Confirmed requirement analysis succeeded and PRD document creation returned `document_id = Ntvmd3ahPopcHmxxgSwcGU4vn0c`, `url = null`.
- Confirmed the publication failure occurred at `card_reply_attempted` with Lark `HTTP 400: field validation failed`.
- Added regression coverage for empty PRD URLs in preview cards and text fallback replies after card send failure.
- Updated preview card rendering to avoid `[打开文档]()` when `docs +create` returns no URL.
- Updated the pipeline success path to send a text fallback reply when `reply_error` is present after PRD card publication fails.
- Verified `tests.test_prd_publish` and `tests.test_pipeline_start` together: 20 tests passed.
- Full `unittest discover` could not complete in the current sandbox because unrelated tests still use Python `tempfile.TemporaryDirectory()` and hit `PermissionError` under both the system temp directory and `.test-tmp`.
