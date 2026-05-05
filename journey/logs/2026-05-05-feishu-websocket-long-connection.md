# 2026-05-05 Feishu WebSocket Long-Connection Architecture Confirmation

## Context

Feishu open platform team announced the "long-connection mode (WebSocket)" as the recommended approach for receiving event callbacks, targeting developers who lack public IP / domain and cannot use traditional Webhook mode.

## Finding

**The DevFlow project already uses the announced approach.** The `lark-cli event consume` command internally establishes a WebSocket full-duplex channel to `wss://open.feishu.cn` and streams events as NDJSON to stdout. No public IP, domain, or webhook callback URL is required.

### Event reception chain

```
devflow start
  → run_start_loop()                    [pipeline.py:1894]
    → listen_bot_events()               [lark_cli.py:194]
      → lark-cli event consume im.message.receive_v1 --as bot
        → WebSocket long-connection → NDJSON event stream  [lark_cli.py:240-316]
```

### Impact assessment

| Dimension | Assessment |
|-----------|-----------|
| Event reception | Already using WebSocket long-connection via lark-cli |
| Code changes | Zero — no modification needed |
| Deployment | Already runs on local/non-public-network environments |
| Official constraints | 3s processing timeout (mitigated by immediate confirmation reply), cluster mode (single-client), enterprise self-built apps only, max 50 connections |

### Future opportunity

If `lark-cli` adds support for consuming `card.callback` events through the same WebSocket channel, the approval interaction can be upgraded from text-based commands (`Approve <run_id>`) to in-card button clicks. This is a deferred improvement tracked in design.md Key Decisions.

## Actions taken

- Updated `journey/design.md`:
  - Added WebSocket long-connection architecture note to Key Decisions (after line 35)
  - Added future card-callback improvement note to checkpoint action channels (after line 62)
  - Updated "Last updated" header
