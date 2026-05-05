# Solution Review Card Validation Plan

## Goal

Fix `devflow start` / checkpoint resume failures where the solution review interactive card reply is rejected by Lark with API code `99992402` and `HTTP 400: field validation failed`.

## Evidence So Far

- Run `20260503T113131Z-om_x100b50476ff5fca4b2d6ad33e58348f-d0866a46` completed requirement intake and solution design.
- The trace fails at `solution_review_card_attempted` / `solution_review_card_failed`.
- `run.json.checkpoint_publication.error` records the Lark validation failure.
- This is distinct from the earlier PRD preview card fallback issue.

## Debug Plan

- Trace the solution review card construction and exact `im +messages-reply` command.
- Compare it with known-valid `im +messages-reply --msg-type interactive --content ...` expectations.
- Add focused regression coverage for the invalid card shape.
- Implement the smallest fix at the card construction boundary.
- Verify with focused tests and then the broader test suite.

