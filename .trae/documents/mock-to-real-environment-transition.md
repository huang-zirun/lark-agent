# 从 MOCK Agent 到真实环境的实施计划

## 概述

将 DevFlow Engine 从当前 MOCK Agent 硬编码闭环过渡到真实 LLM Provider 驱动的完整交付管道。当前系统通过 `use_mock=True` 硬编码走 MOCK_AGENTS 路径，需要改造为 Provider 配置驱动的自动切换，并补全真实环境所需的代码上下文注入、结构化输出校验/修复、测试真实执行、错误重试、日志增强等能力。

---

## Step 1: 移除 `use_mock` 硬编码，改为 Provider 配置驱动

### 目标
消除 `use_mock=True` 硬编码，让系统根据 Provider 配置自动决定执行路径。

### 改动文件

1. **`backend/app/core/execution/stage_runner.py`**
   - 移除 `execute_stage()` 的 `use_mock` 参数
   - 改为通过 `resolve_provider()` 判断：如果返回的是 MockProvider 实例则走 mock 路径，否则走 `run_agent()` 真实路径
   - 具体逻辑：在 `execute_stage()` 内部，先尝试 `resolve_provider(session, provider_id=stage_run.resolved_provider_id)`，判断返回实例类型决定路径

2. **`backend/app/core/execution/executor.py`**
   - 移除 `run_pipeline_stages()` 的 `use_mock` 参数
   - 传递 `execute_stage()` 调用时不传 `use_mock`

3. **`backend/app/api/routes_pipeline.py`**
   - `start_pipeline()` 和 `resume_pipeline()` 中移除 `use_mock=True` 参数
   - 改为从请求体或环境配置读取 provider 选择

4. **`backend/app/schemas/pipeline.py`**
   - `PipelineRunCreate` 增加 `use_mock: bool = False` 字段（向后兼容，默认走真实路径）

### 验证标准
- 不传任何 Provider 配置时，自动降级到 MockProvider，流程正常运行
- 配置了 OpenAI/Anthropic Provider 后，自动走 `run_agent()` 路径

---

## Step 2: 增强 Provider 接口（重试、超时、Token 计量）

### 目标
让 Provider 层具备生产级的健壮性：指数退避重试、可配置超时、Token 用量记录。

### 改动文件

1. **`backend/app/core/provider/base.py`**
   - `LLMProvider` Protocol 增加 `generate_with_retry()` 方法签名
   - 增加 `LLMCallResult` 数据类，包含 `content`、`usage`（prompt_tokens/completion_tokens）、`latency_ms`、`model`

2. **`backend/app/shared/config.py`**
   - Settings 增加：`LLM_TIMEOUT_SECONDS: int = 120`、`LLM_MAX_RETRIES: int = 3`、`LLM_RETRY_BASE_DELAY: float = 1.0`

3. **`backend/app/core/provider/openai_compatible.py`**
   - 实现指数退避重试：对 429（读取 Retry-After）、5xx 进行重试；401/403 立即失败
   - 从响应中提取 `usage` 字段
   - 超时从 settings 读取
   - 增加 `structured_output` 降级：当 `response_format.json_schema` 不可用时，降级为 prompt 注入 schema + JSON 解析

4. **`backend/app/core/provider/anthropic.py`**
   - 实现指数退避重试：对 429、5xx 重试；401/403 立即失败
   - 从响应中提取 `usage` 字段
   - 超时从 settings 读取
   - 增强 JSON 提取：处理 markdown code block 包裹的 JSON

5. **`backend/app/core/provider/mock_provider.py`**
   - 实现 `generate_with_retry()`（直接调用 `generate()`）
   - 返回 `LLMCallResult` 格式

### 验证标准
- 模拟 429 响应时，能等待后重试
- 模拟 401 响应时，立即抛出异常不重试
- 每次调用记录 token 用量和延迟

---

## Step 3: 实现代码上下文注入

### 目标
让 design_agent 和 code_patch_agent 能获取 workspace 中的实际代码内容，而非仅依赖 artifact 数据。

### 改动文件

1. **`backend/app/core/workspace/workspace_manager.py`**
   - 新增 `get_directory_tree(workspace_path, max_depth=3, exclude_dirs=None) -> dict` 方法
     - 返回树形目录结构，排除 .git、node_modules、__pycache__、.venv 等
   - 新增 `read_file_content(workspace_path, file_path, max_lines=200) -> str | None` 方法
     - 读取指定文件内容，限制行数防止 token 爆炸
   - 新增 `get_code_context(workspace_path, affected_files: list[str]) -> dict` 方法
     - 组合目录树 + 关键文件内容，返回结构化上下文

2. **`backend/app/core/execution/stage_runner.py`**
   - `_assemble_input()` 增加代码上下文组装逻辑：
     - `solution_design` 阶段：注入目录树 + requirement_brief
     - `code_generation` 阶段：注入 design_spec 中 affected_files 对应的文件内容 + 目录树
     - `test_generation_and_execution` 阶段：注入 change_set + 目录树
   - 从 `PipelineRun.workspace_ref_id` 获取 workspace，读取代码上下文

3. **`backend/app/schemas/agent_outputs.py`**
   - `CodeContext` 模型定义：`directory_tree: dict | None`、`file_contents: dict[str, str] | None`
   - 更新 `DesignAgentInput`、`CodePatchAgentInput`、`TestAgentInput` 的 `code_context` 字段类型

### 验证标准
- solution_design 阶段的 input_data 包含 workspace 目录树
- code_generation 阶段的 input_data 包含 affected_files 的实际内容
- 无 workspace 时不注入代码上下文，流程不中断

---

## Step 4: 增强 Schema 校验与 LLM 输出修复

### 目标
将当前 schema 校验失败仅 warning 的行为改为：尝试修复 → 修复失败则重试 → 重试耗尽则失败。

### 改动文件

1. **`backend/app/agents/runner.py`**
   - 新增 `_validate_and_fix_output(result: dict, schema_cls) -> dict` 函数
     - 先 `model_validate()`，通过则直接返回
     - 失败则尝试修复：补缺失的默认值字段、类型强转、枚举值映射
     - 修复后再校验，仍失败则抛出 `OutputValidationError`
   - `run_agent()` 中调用 `_validate_and_fix_output()`
   - 增加 LLM 输出重试逻辑：校验失败时，将错误信息附加到 prompt 重新调用，最多重试 2 次

2. **`backend/app/shared/errors.py`**
   - 新增 `OutputValidationError(DevFlowError)` 错误类

3. **`backend/app/core/execution/stage_runner.py`**
   - 移除当前的 `logger.warning` schema 校验逻辑（L59-64）
   - schema 校验责任上移到 `runner.py`

### 验证标准
- LLM 返回缺少必填字段时，能补默认值修复
- LLM 返回完全无效 JSON 时，触发重试
- 重试 2 次仍失败时，StageRun 标记为 failed

---

## Step 5: 实现 test_agent 的真实执行

### 目标
test_generation_and_execution 阶段不再返回假数据，而是：LLM 生成测试代码 → apply 测试 patch → 在 workspace 中执行测试命令 → 捕获真实结果。

### 改动文件

1. **`backend/app/core/execution/stage_runner.py`**
   - 新增 `_execute_test_stage()` 专用函数，编排三步子流程：
     1. 调用 `run_agent("test_agent", ...)` 生成测试 change_set
     2. 将测试文件写入 workspace（使用 `patch_applier.apply_patch()`）
     3. 调用 `command_runner.run_command()` 执行测试命令
     4. 将真实执行结果组装为 `test_report` artifact
   - `execute_stage()` 中对 `stage_key == "test_generation_and_execution"` 走专用路径

2. **`backend/app/shared/config.py`**
   - 新增 `TEST_COMMAND: str = "uv run pytest -xvs"` 默认测试命令
   - 新增 `TEST_TIMEOUT: int = 300` 测试执行超时

3. **`backend/app/agents/profiles.py`**
   - 更新 `test_agent` 的 system_prompt：明确要求生成测试代码的 change_set 格式，而非直接生成 test_report

### 验证标准
- test 阶段在 workspace 中实际生成测试文件
- 测试命令真实执行，stdout/stderr/exit_code 来自真实运行
- 测试失败不阻塞流程，结果如实记录

---

## Step 6: 增强错误处理与日志系统

### 目标
建立结构化日志、LLM 调用追踪、错误分类处理。

### 改动文件

1. **`backend/app/shared/logging.py`**
   - 增加结构化日志格式：JSON 格式输出，包含 run_id、stage_key、provider 等上下文
   - 增加文件日志：按日期轮转，存储到 `data/logs/` 目录
   - 增加 `get_context_logger(name, **context)` 工厂函数，绑定上下文字段

2. **`backend/app/agents/runner.py`**
   - 记录每次 LLM 调用的：provider_id、model、prompt_tokens、completion_tokens、latency_ms、success
   - 敏感信息过滤：API Key 脱敏、prompt 内容截断

3. **`backend/app/core/provider/openai_compatible.py`** 和 **`anthropic.py`**
   - 错误响应保留完整信息（移除 `[:200]` 截断），存入 raw_response_path
   - 区分错误类型：`AuthenticationError`、`RateLimitError`、`ServerError`、`NetworkError`

4. **`backend/app/shared/errors.py`**
   - 新增细粒度错误类：`AuthenticationError`、`RateLimitError`、`OutputValidationError`

5. **`backend/app/core/pipeline/orchestrator.py`**
   - `handle_stage_failure()` 增加退避延迟：`asyncio.sleep(2 ** attempt)`
   - 记录重试原因到 StageRun.error_message

### 验证标准
- 日志文件按日期生成在 data/logs/ 目录
- LLM 调用日志包含 token 用量和延迟
- API Key 在日志中脱敏

---

## Step 7: 环境配置与 Provider 自动初始化

### 目标
应用启动时自动从环境变量创建默认 Provider 配置，支持一键切换 mock/真实环境。

### 改动文件

1. **`backend/app/shared/config.py`**
   - Settings 增加：
     - `DEFAULT_PROVIDER_TYPE: str = "mock"`（可选 mock/openai/anthropic）
     - `OPENAI_API_KEY: str = ""`
     - `OPENAI_API_BASE: str = "https://api.openai.com/v1"`
     - `OPENAI_DEFAULT_MODEL: str = "gpt-4o"`
     - `ANTHROPIC_API_KEY: str = ""`
     - `ANTHROPIC_DEFAULT_MODEL: str = "claude-sonnet-4-20250514"`

2. **`backend/app/db/base.py`**
   - `init_db()` 末尾增加 `_ensure_default_providers(session)` 调用
   - 新增 `_ensure_default_providers()`：根据环境变量自动创建 Provider 配置记录（如已存在则跳过）

3. **`.env.example`**
   - 更新为包含所有新配置项的完整示例

### 验证标准
- 设置 `DEFAULT_PROVIDER_TYPE=openai` + `OPENAI_API_KEY=sk-xxx` 后启动，自动创建 OpenAI Provider
- 不设置任何 API Key 时，默认使用 MockProvider
- Provider 配置持久化到 SQLite，重启后不丢失

---

## Step 8: 编写单元测试

### 目标
为核心模块建立单元测试覆盖，确保真实环境改造不破坏现有功能。

### 新增文件

1. **`backend/tests/test_state_machine.py`**
   - PipelineRunStateMachine 所有合法/非法转换
   - StageRunStateMachine 所有合法/非法转换

2. **`backend/tests/test_schemas.py`**
   - 每个 Artifact schema 的合法输入验证
   - 非法输入（缺失字段、错误枚举值、类型错误）验证

3. **`backend/tests/test_provider.py`**
   - MockProvider.generate() 和 validate()
   - OpenAICompatibleProvider 的 HTTP 错误处理（mock httpx）
   - AnthropicProvider 的 JSON 提取逻辑

4. **`backend/tests/test_runner.py`**
   - `_build_prompt()` 输出格式
   - `_validate_and_fix_output()` 修复逻辑

5. **`backend/tests/test_patch_applier.py`**
   - apply_patch 正常/冲突/3way 场景

6. **`backend/tests/test_workspace.py`**
   - `get_directory_tree()` 排除规则
   - `read_file_content()` 行数限制

### 验证标准
- `uv run pytest` 全部通过
- 核心模块测试覆盖率 > 70%

---

## Step 9: Workspace 阶段快照与回滚增强

### 目标
每个阶段执行前在 workspace 中 git commit，确保可回滚到任意阶段状态。

### 改动文件

1. **`backend/app/core/workspace/workspace_manager.py`**
   - 新增 `snapshot_workspace(workspace_path, message) -> str` 方法
     - `git add -A && git commit -m "snapshot: {message}"`
   - 新增 `restore_workspace_snapshot(workspace_path, commit_hash)` 方法
     - `git reset --hard {commit_hash}`

2. **`backend/app/core/execution/stage_runner.py`**
   - `execute_stage()` 开始前调用 `snapshot_workspace()`
   - 阶段失败时可选调用 `restore_workspace_snapshot()` 回滚

### 验证标准
- 每个阶段执行后 workspace 有对应 snapshot commit
- 阶段失败回滚后 workspace 恢复到上一阶段状态

---

## 实施顺序与依赖关系

```
Step 1 (移除 use_mock) ──→ Step 7 (环境配置)
    │                          │
    ↓                          ↓
Step 2 (Provider 增强) ──→ Step 3 (代码上下文)
    │                          │
    ↓                          ↓
Step 4 (Schema 校验)     Step 5 (测试真实执行)
    │                          │
    ↓                          ↓
Step 6 (错误处理/日志) ←───────┘
    │
    ↓
Step 8 (单元测试)
    │
    ↓
Step 9 (Workspace 快照)
```

**建议实施顺序**：1 → 7 → 2 → 3 → 4 → 5 → 6 → 8 → 9

Step 1 和 7 是基础，必须先完成；Step 2-5 是核心功能改造，可并行但建议顺序执行；Step 6 是质量保障；Step 8 是验证；Step 9 是增强。

---

## 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| LLM 输出格式不稳定 | Step 4 的修复+重试机制；保留 Mock 降级路径 |
| 代码上下文超出 token 限制 | Step 3 中限制目录树深度和文件内容行数 |
| 测试执行破坏 workspace | Step 9 的 snapshot 机制；测试在隔离 workspace 执行 |
| Provider API 不可用 | Step 2 的重试+降级；Step 7 的环境变量快速切换 |
| Windows 路径/编码问题 | 所有文件操作显式指定 utf-8；路径使用 Path 对象 |

---

## 回滚策略

- 任何步骤出问题可通过 `DEFAULT_PROVIDER_TYPE=mock` 立即回退到 MOCK 模式
- 每个 Step 完成后独立可验证，不需要后续 Step 才能测试
- Workspace 快照确保代码变更可回滚
- 数据库变更均为新增字段/表，无破坏性迁移
