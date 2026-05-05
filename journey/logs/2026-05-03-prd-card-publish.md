# PRD Card Publish Log

## 2026-05-03

- Started implementation from the approved PRD document and preview card plan.
- Confirmed current pipeline replies with text only and Lark shortcuts support `docs +create --as bot --markdown` plus `im +messages-reply --msg-type interactive --content`.
- Added focused TDD coverage for PRD Markdown rendering, Lark command construction, pipeline publication success, and publication failure semantics.
- Implemented deterministic PRD rendering, interactive preview card JSON, bot-owned PRD document creation, and card reply publishing.
