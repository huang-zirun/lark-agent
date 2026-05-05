# Bot PRD Card Fallback Plan

## Summary

Investigate and fix the bot-visible response gap when a `devflow start` run completes requirement intake but the PRD preview card reply fails validation.

## Evidence

- The affected run completed `requirement_intake` successfully and wrote `requirement.json`.
- `docs +create` succeeded but returned a `document_id` with `url = null`.
- The interactive card reply failed with Lark API code `99992402` and `HTTP 400: field validation failed`.
- The pipeline records the publication failure but does not send a text fallback because the overall run status remains `success`.

## Hypothesis

The preview card builds a Markdown link with an empty PRD URL (`[打开文档]()`), which Lark rejects during interactive card validation. After that failure, the success path has no text fallback, so the user sees no useful bot response for that message.

## Test Plan

- Add a card-rendering regression test that verifies empty PRD URLs do not produce empty Markdown links.
- Add a pipeline regression test that verifies card publication failure triggers a text fallback reply.
- Run the focused PRD publication tests.

## Scope

- Keep requirement intake and PRD document creation behavior unchanged.
- Do not change the machine-readable artifact schema.
- Keep the fix limited to preview-card rendering and bot reply fallback behavior.
