# 代码评审节点验证计划

## 背景

代码评审（code_review）节点已位于测试生成（test_generation）之后，流水线顺序为：
`requirement_intake → solution_design → (人工审批) → code_generation → test_generation → code_review → (人工确认) → delivery`

需要验证代码评审是否能正确调通，使用已有的实验数据进行端到端验证。

## 可用实验数据

| 运行 ID | requirement | solution | code-generation | test-generation | 备注 |
|---------|------------|----------|----------------|----------------|------|
| `20260503T175301Z-...-2347d7cf` | ✅ | ✅ | ✅ (status=success) | ✅ (status=success) | **最佳候选**，四件上游产物齐全，workspace 仍存在 |
| `20260504T024548Z-...-f26fdc47` | ✅ | ✅ | ✅ (status=success) | ❌ (test_generation 失败) | 无法用于代码评审验证 |
| `20260504T063445Z-...-6a855c22` | ✅ | ✅ | ✅ (status=success) | ❌ (test_generation 失败) | 无法用于代码评审验证 |

工作区 `D:\lark\workspaces\snake-game` 仍存在，包含 `index.html`、`README.md`、`test.html`。

## 验证步骤

### 步骤 1：运行现有单元测试

运行 `uv run python -m pytest tests/test_code_review.py -v`，确认现有 3 个代码评审单元测试全部通过：
- `test_review_tools_are_read_only` — 验证评审工具只允许只读操作
- `test_code_review_agent_returns_passed_artifact` — 验证评审通过场景
- `test_failed_test_command_becomes_blocking_review_evidence` — 验证测试失败自动升级为阻塞发现
- `test_render_markdown_and_cli_generate_review` — 验证 Markdown 渲染和 CLI 生成

### 步骤 2：使用实验数据运行 CLI 代码评审

使用运行 `20260503T175301Z-om_x100b504cf91710a0b2684bda1f50133-2347d7cf` 的已有产物，通过 CLI 命令触发代码评审：

```powershell
uv run python -m devflow review generate --run 20260503T175301Z-om_x100b504cf91710a0b2684bda1f50133-2347d7cf
```

> 注意：该 run.json 中 `code_generation_artifact` 和 `test_generation_artifact` 字段缺失，但 CLI 会回退到 `run_dir / "code-generation.json"` 和 `run_dir / "test-generation.json"`，因此 `--run` 模式仍可工作。

验证要点：
- 命令成功退出（exit code 0）
- 生成 `code-review.json`，schema_version 为 `devflow.code_review.v1`
- 生成 `code-review.md`，包含评审摘要、问题列表、修复建议和人工决策指令
- `review_status` 为 `passed` 或 `needs_changes`
- `quality_gate` 包含 `passed`、`blocking_findings`、`risk_level`
- `test_summary` 正确反映测试命令结果
- `tool_events` 记录了评审过程中的只读工具调用

### 步骤 3：验证代码评审产物内容

检查生成的 `code-review.json`：
- `inputs` 字段正确引用四件上游产物路径
- `findings` 列表格式正确（每个 finding 包含 id、severity、category、title、description、blocking 等字段）
- `diff_summary` 包含 changed_files、code_diff_bytes、test_diff_bytes
- `repair_recommendations` 和 `warnings` 为列表类型

检查生成的 `code-review.md`：
- 标题为 `# 代码评审：<run_id>`
- 包含评审状态、质量门禁、阻塞问题数、风险等级
- 包含问题列表（如有）
- 包含修复建议
- 包含 `Approve <run_id>` 和 `Reject <run_id>` 人工决策指令

### 步骤 4：验证流水线自动链接

确认 `pipeline.py` 中的调用链：
1. `run_code_generation_after_approval` → `run_test_generation_after_code_generation` → `run_code_review_after_test_generation`
2. `run_code_review_after_test_generation` 在评审完成后调用 `publish_code_review_checkpoint`
3. `should_auto_repair_review` 在首次评审不通过且未超过一次修复时触发自动修复
4. `run_repair_after_code_review` 重新执行 code_generation → test_generation → code_review（allow_auto_repair=False）

通过阅读代码确认以上链接关系正确，无需修改代码。

### 步骤 5：验证代码评审检查点流程

确认 `approve_checkpoint_run` 中对 `code_review` 阶段的处理：
- 当 checkpoint stage 为 `code_review` 且决策为 approve 时，run status 设为 `success`，不再继续执行后续阶段
- 当 checkpoint stage 为 `code_review` 且决策为 reject 且 repair_attempts < 1 时，触发自动修复
- 当 checkpoint stage 为 `code_review` 且决策为 reject 且 repair_attempts >= 1 时，run status 设为 `blocked`

### 步骤 6：运行完整测试套件

运行 `uv run python -m pytest -v`，确认所有 99+ 测试通过，无回归。

## 风险与注意事项

1. **LLM 调用成本**：步骤 2 会发起真实 LLM 请求，可能产生 token 费用
2. **LLM 限流**：之前实验中出现过 HTTP 429 限流错误，如果遇到可稍后重试
3. **工作区一致性**：`D:\lark\workspaces\snake-game` 的文件可能已被后续运行修改，代码评审会读取当前工作区状态而非快照
4. **run.json 状态不一致**：第一个实验运行的 run.json 中 code_generation 和 test_generation 阶段仍为 pending，但实际产物文件存在。CLI 的回退逻辑可以处理此情况
