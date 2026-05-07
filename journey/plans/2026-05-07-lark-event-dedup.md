# 修复飞书事件重复消费

## 目标

修复同一条飞书消息被 `lark-cli event consume` 推送两次导致创建两个重复 pipeline run 的问题。

## 根因

- 飞书开放平台的 `im.message.receive_v1` 事件可能因网络重试产生重复推送
- 整个事件处理链路中没有任何基于 `message_id` 的去重机制
- `new_run_id()` 包含随机 uuid 部分，每次调用生成不同 run ID，无法天然去重
- 实测：同一个 `message_id: om_x100b508211ed5ca4b4a6a5cdc690c1e` 在 63ms 内被消费两次，创建了两个独立 run

## 修复方案

在 `iter_lark_cli_event_stream` 中维护 `seen_message_ids` 集合，基于事件的 `message_id` 跳过重复事件。这是最前端的过滤点，能防止重复事件流入后续的 MessageBuffer 和 UserMessageQueue。

### 为什么选择在事件流层去重

1. **最前端拦截**：重复事件在最源头被丢弃，不会消耗任何下游资源
2. **不侵入业务逻辑**：MessageBuffer、UserMessageQueue、process_bot_event 无需修改
3. **一致性好**：`event_to_source` 已有提取 `message_id` 的逻辑，直接复用
4. **边界清晰**：去重只关心"同一条消息是否已见过"，不关心消息内容

### 实施步骤

1. 在 `iter_lark_cli_event_stream` 中添加 `seen_message_ids: set[str]` 参数
2. 对每个 yield 前的事件，提取 `message_id` 并检查是否已见过
3. 重复事件跳过并记录（可选用 logging）
4. 在 `listen_bot_events` 中传入新的 `seen_message_ids` 集合
5. 编写测试覆盖重复事件场景

## 验收

- 同一 `message_id` 的事件只被处理一次
- 不同 `message_id` 的事件正常处理
- 无 `message_id` 的事件（如 fallback event-id）仍然正常处理
- 现有测试全部通过
