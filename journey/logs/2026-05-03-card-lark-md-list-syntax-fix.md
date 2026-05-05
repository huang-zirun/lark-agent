# 交互卡片 99992402 修复日志

## 2026-05-03

### 问题

`devflow start` 发送交互式卡片（PRD 预览卡片和方案评审卡片）时，Lark API 返回错误码 `99992402`，消息为 "HTTP 400: field validation failed"。

### 根因分析（两轮修复）

#### 第一轮修复：lark_md 列表语法

1. **关键发现**：运行 `20260503T083136Z-om_x100b504430477ca8b27d69a309552e8-3372214a` 显示 PRD 卡片在有有效 URL 的情况下仍然失败。

2. **共同模式**：两张卡片都使用 `lark_md` 类型的 `text` 元素，且内容中包含 `- ` 前缀的无序列表语法。

3. **文档依据**：飞书卡片 Markdown 文档明确指出，**无序列表（`- item`）仅支持 Markdown 组件，不支持 `lark_md` 文本元素**。

4. **修复**：将所有 `lark_md` 中的 `- ` 替换为 `• `（Unicode 项目符号）。

#### 第二轮修复：idempotency key 过长（真正根因）

1. **关键发现**：运行 `20260503T123303Z-om_x100b5040493c3938b21603e79c5587f-c58e7ef9` 在列表语法修复后仍然失败。

2. **实验验证**：通过 lark-cli 直接发送测试卡片，发现：
   - 使用 24 字符的 key：`devflow-checkpoint-12345` → **成功**
   - 使用 69 字符的 key：`devflow-20260503T123303Z-om_x100b5040493c3938b21603e79c5587f-c58e7ef9` → **失败 (99992402)**
   - 使用 80 字符的 key：`devflow-...-checkpoint` → **失败 (99992402)**

3. **结论**：**Lark API 对 idempotency key 有长度限制（约 64 字符）**。当前代码使用 `f"devflow-{run_id}-suffix"` 格式，run_id 本身约 50 字符，总长度 70-80 字符，超过限制。

### 修复内容

#### 1. 替换 `lark_md` 中的 `- ` 列表语法为 `• `

- **prd.py**：`_preview_list` 和 `_preview_acceptance` 中所有 `- ` → `• `
- **checkpoint.py**：`build_solution_review_card` 中所有 `- ` → `• `

#### 2. 缩短 idempotency key 长度

- **pipeline.py**：新增 `_idempotency_key(run_id, suffix)` 辅助函数，使用 run_id 的最后 8 位（UUID 片段）生成短 key，格式为 `df-{short_id}-{suffix}`，硬上限 64 字符
- 替换所有 8 处长 key 的使用：
  - PRD 卡片：`df-{short_id}-prd-card`
  - 方案评审卡片：`df-{short_id}-solution-review`
  - fallback 文本：`df-{short_id}-{status}-fallback`
  - checkpoint resume：`df-{short_id}-checkpoint-resume`
  - checkpoint approved：`df-{short_id}-checkpoint-approved`
  - reject reason：`df-{short_id}-reject-reason`
  - checkpoint rerun：`df-{short_id}-rerun-{attempt}`
  - checkpoint missing：`df-{short_id}-missing`

#### 3. 为方案评审卡片添加文本回退

- **pipeline.py**：`publish_solution_review_checkpoint` 中卡片失败时设置 `reply_error`
- **pipeline.py**：`resume_blocked_solution_design` 和 `rerun_solution_design_after_reject` 的文本回复中附带卡片失败提示
- **pipeline.py**：文本回复异常时捕获 `LarkCliError` 并记录错误到 `run_payload`

#### 4. 回归测试

- **test_prd_publish.py**：`test_preview_card_does_not_use_dash_list_syntax_in_lark_md`
- **test_checkpoint.py**：`test_solution_review_card_does_not_use_dash_list_syntax_in_lark_md`
- **test_checkpoint.py**：`test_publish_solution_review_checkpoint_sets_reply_error_on_card_failure`
- 更新现有测试以适配新的短 idempotency key 格式

### 验证

- 全部 82 个测试通过
- lark-cli 直接发送验证：短 key (`df-c58e7ef9-solution-review`, 29 chars) 成功发送卡片

### 相关文件

- `devflow/prd.py`
- `devflow/checkpoint.py`
- `devflow/pipeline.py`
- `tests/test_prd_publish.py`
- `tests/test_checkpoint.py`
- `tests/test_pipeline_start.py`
