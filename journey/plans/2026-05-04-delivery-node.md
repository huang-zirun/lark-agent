# Delivery Node Implementation Plan

## Goal

Implement the sixth DevFlow node, `delivery-agent`, after the code review human checkpoint is approved.

## Implementation

- Add `devflow.delivery` with `devflow.delivery.v1` JSON output and deterministic Markdown rendering.
- Generate a delivery package only: `delivery.json`, `delivery.md`, and `delivery.diff`; do not create branches, commits, pushes, or PRs.
- Validate upstream artifacts and require the current checkpoint to be the approved `code_review` checkpoint.
- Capture Git state when available: current branch, HEAD, status entries, tracked diff, untracked text-file patches, and diff statistics.
- Mark non-Git workspaces or blocked verification as not ready to merge while still producing a reviewable package.
- Wire code-review approval through bot, CLI decision, and approval polling to run delivery and set the `delivery` stage to `success`.
- Add `devflow delivery generate --run <run_id>` for manual package generation.
- Update README and `journey/design.md` to make delivery the final implemented node.

## Tests

- Add `tests/test_delivery.py` for Git, non-Git, readiness, and validation behavior.
- Extend `tests/test_pipeline_start.py` for code-review approve delivery generation and reject non-delivery behavior.
- Add CLI coverage for `devflow delivery generate --run <run_id>`.

## Verification

```powershell
uv run pytest tests/test_delivery.py tests/test_pipeline_start.py tests/test_checkpoint.py -q -p no:cacheprovider
uv run python -m compileall devflow
```

## Assumptions

- The v1 delivery node is package-only.
- Merge readiness is advisory and recorded in the delivery artifact.
- Untracked binary or oversized files are listed with warnings instead of embedded patches.
