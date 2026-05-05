# 修复交互卡片 99992402 "field validation failed" 错误

## 问题

`devflow start` 在发送交互式卡片（PRD 预览卡片和方案评审卡片）时，Lark API 返回错误码 `99992402`，消息为 "HTTP 400: field validation failed"。

## 根因分析

### 关键证据

1. **PRD 卡片和方案评审卡片都失败**：运行 `20260503T083136Z-om_x100b504430477ca8b27d69a309552e8-3372214a` 显示 PRD 卡片在有有效 URL 的情况下仍然失败（`publication.card_reply.status: "failed"`，错误码 `99992402`）。这说明之前的"空 URL"修复只解决了次要问题，根因是两张卡片共有的。

2. **纯文本回复正常**：`build_workspace_blocked_reply`、`build_success_reply`、`build_failure_reply` 等纯文本回复都能成功发送，说明 `send_bot_reply` 路径没有问题，问题出在 `send_bot_card_reply` 发送的交互卡片内容上。

3. **两张卡片共同的 `lark_md` 内容模式**：
   - 都使用 `- ` 前缀表示列表项
   - 都使用 `**bold**` 加粗文本
   - 都使用 `\n` 换行

### 根因假设

根据[飞书卡片 Markdown 文档](https://open.feishu.cn/document/common-capabilities/message-card/message-cards-content/using-markdown-tags)，**无序列表（`- item`）仅支持 Markdown 组件，不支持 `lark_md` 文本元素**。文档明确指出：

> 有序列表、无序列表等 markdown 语法必须放在富文本组件中才能生效。

在 `lark_md` 类型的 `text` 元素中使用 `- ` 列表语法，可能导致 Lark API 的字段验证失败，返回 `99992402` 错误。

### 受影响代码

| 文件 | 函数 | 问题 |
|------|------|------|
| [prd.py](../devflow/prd.py) | `_preview_list` | 使用 `f"- {item}"` 生成列表项 |
| [prd.py](../devflow/prd.py) | `_preview_acceptance` | 使用 `f"- {criterion_id}：{criterion}"` 生成列表项 |
| [checkpoint.py](../devflow/checkpoint.py) | `build_solution_review_card` | 使用 `f"- `{path}`：{responsibility}"` 生成文件变更列表 |

## 修复方案

### 步骤 1：替换 `lark_md` 中的 `- ` 列表语法

将所有 `lark_md` 内容中的 `- ` 前缀替换为 `• `（Unicode 项目符号），这是 `lark_md` 中安全的纯文本格式：

**prd.py**：
- `_preview_list`：`f"- {item}"` → `f"• {item}"`
- `_preview_acceptance`：`f"- {criterion_id}：{criterion}"` → `f"• {criterion_id}：{criterion}"`，`f"- AC-{index:03d}：..."` → `f"• AC-{index:03d}：..."`，`f"- 暂无"` → `f"• 暂无"`

**checkpoint.py**：
- `build_solution_review_card`：`f"- `{path}`：{responsibility}"` → `f"• `{path}`：{responsibility}"`，`"- 暂无文件变更清单"` → `"• 暂无文件变更清单"`

### 步骤 2：为方案评审卡片添加文本回退

在 `publish_solution_review_checkpoint`（pipeline.py）中，当卡片发送失败时，发送文本回退回复，确保用户仍能收到可见消息。参照 PRD 卡片的文本回退模式（pipeline.py 第 293 行）：

```python
should_send_text_reply = run_payload["status"] != "success" or run_payload.get("reply_error") is not None
```

在 `resume_blocked_solution_design` 和 `rerun_solution_design_after_reject` 中，检查 `checkpoint_publication` 状态，如果卡片发送失败则追加文本回退。

### 步骤 3：添加回归测试

在 `tests/test_prd_publish.py` 中添加：
- 测试 PRD 卡片不包含 `- ` 列表语法
- 测试方案评审卡片不包含 `- ` 列表语法
- 测试方案评审卡片发送失败时发送文本回退

### 步骤 4：验证修复

- 运行 `uv run python -m pytest tests/test_prd_publish.py tests/test_pipeline_start.py -v`
- 运行 `uv run devflow start --once` 进行实际验证

## 不在范围内

- 不修改机器可读的 artifact JSON schema
- 不修改 `send_bot_card_reply` 或 `send_bot_reply` 的调用方式
- 不升级 `lark-cli` 版本
