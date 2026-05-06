# API 驱动的端到端验证实验设计与行业调研

> 调研日期：2026-05-06
> 目标：设计简单/中等/复杂三个层级的实验，通过 REST API 验证 DevFlow Engine 的端到端交付能力

---

## 一、行业调研：AI 驱动开发流水线验证实践

### 1.1 基准方法论

| 基准 | 任务粒度 | 评估方式 | 局限性 |
|------|----------|----------|--------|
| **SWE-bench** (Princeton, 2023) | 仓库级 Issue 修复 | 测试执行通过率 | 仅 Python，依赖测试覆盖度 |
| **SWE-bench Verified** | 500 个人工验证子集 | 同上 | 子集规模有限 |
| **HumanEval** (OpenAI, 2021) | 单函数补全 | pass@k | 不涉及多文件/工程场景 |
| **LiveCodeBench** (2024) | 编程竞赛题 | 测试执行 | 偏算法，非工程 |
| **DevBench** (2024) | 全流程开发 | 功能+质量 | 规模小 |
| **WebArena** (CMU, 2023) | Web 环境任务 | 任务完成率 | 仅 Web 交互 |

**核心启示**：SWE-bench 是目前最接近"现场命题挑战"场景的基准——给定需求描述，在真实代码库中完成端到端修复。但 SWE-bench 侧重"修复"而非"新功能开发"，DevFlow 需要验证的是后者。

### 1.2 编排系统评估方法

| 系统 | 评估方法 | 核心指标 |
|------|----------|----------|
| **MetaGPT** | 端到端游戏开发（贪吃蛇/弹球） | 可执行率、需求满足度 |
| **ChatDev** | 70 个需求测试 | 可执行率、对话轮数、代码行数 |
| **AutoGen** | 多任务完成率 | 任务完成率、对话效率、token 成本 |
| **OpenDevin/SWE-agent** | SWE-bench | Issue 解决率 |

**核心启示**：编排系统的评估需同时关注两个维度——(1) 流程正确性（Pipeline 是否按预期流转）；(2) 输出质量（最终代码是否可用）。MetaGPT 的"从一句话到可运行游戏"是最接近比赛验收场景的验证方式。

### 1.3 分层验证架构

```
L3: 端到端集成验证 — 真实 LLM + 真实工具链 + 人工评审
L2: Agent 交互验证 — Mock LLM + 真实编排逻辑
L1: 单元级验证 — JSON Schema 校验 + 工具函数测试
```

**核心启示**：三层架构平衡了成本、速度和覆盖度。本次验证聚焦 L3 层（端到端），因为比赛验收就是 L3 场景。

### 1.4 评估器选择策略

| 评估对象 | 推荐评估器 | 理由 |
|----------|-----------|------|
| 代码生成 | 测试执行 | 最客观 |
| 需求分析/方案设计 | 人工评审 | 结构化质量难以自动评判 |
| 代码评审 | 与人工评审对比 | Cohen's Kappa 一致性 |
| 交付产物 | Schema 校验 + diff 统计 | 结构化可自动验证 |

### 1.5 Seedance Code 2.0 适配要点

- Seedance Code 2.0 作为后台配置的 LLM Provider，需通过 `config.json` 的 `llm.provider` 字段指定
- API 调用时可通过 `provider` 字段覆盖运行时 Provider
- 需验证 Seedance Code 2.0 在代码生成和测试生成阶段的表现（这两个阶段对代码能力要求最高）
- 建议在实验中记录各阶段的 token 消耗和响应时间，用于评估 Provider 性能

---

## 二、实验设计

### 实验前提

- DevFlow API 服务器运行在 `http://127.0.0.1:8080`
- `config.json` 中 `workspace.root` 指向 DevFlow 项目根目录（`d:\lark`）
- `workspace.default_repo` 配置为 DevFlow 项目自身
- LLM Provider 使用 Seedance Code 2.0（通过 `config.json` 或 API `provider` 参数指定）

### 统一执行协议

```powershell
# 步骤 1: 创建 Pipeline
$createBody = @{ requirement_text = "<需求描述>" } | ConvertTo-Json
$create = Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/v1/pipelines" -Method Post -ContentType "application/json" -Body $createBody
$runId = $create.run_id
Write-Host "创建运行: $runId"

# 步骤 2: 触发执行
Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/v1/pipelines/$runId/trigger" -Method Post

# 步骤 3: 轮询状态直到检查点
do {
    Start-Sleep -Seconds 5
    $status = Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/v1/pipelines/$runId"
} while ($status.lifecycle_status -notin @("waiting_approval", "waiting_approval_with_warnings", "delivered", "failed", "terminated"))

# 步骤 4: 查看检查点
$checkpoint = Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/v1/pipelines/$runId/checkpoint"

# 步骤 5: 审批（方案设计检查点）
$approveBody = @{ decision = "approve" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/v1/pipelines/$runId/checkpoint" -Method Post -ContentType "application/json" -Body $approveBody

# 步骤 6: 轮询直到第二个检查点或完成
do {
    Start-Sleep -Seconds 5
    $status = Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/v1/pipelines/$runId"
} while ($status.lifecycle_status -notin @("waiting_approval", "waiting_approval_with_warnings", "delivered", "failed", "terminated"))

# 步骤 7: 审批（代码评审检查点）
Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/v1/pipelines/$runId/checkpoint" -Method Post -ContentType "application/json" -Body $approveBody

# 步骤 8: 等待完成并获取结果
do {
    Start-Sleep -Seconds 5
    $status = Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/v1/pipelines/$runId"
} while ($status.status -notin @("delivered", "failed", "terminated"))

# 步骤 9: 获取详情和 Diff
$detail = Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/v1/metrics/runs/$runId/detail"
$diff = Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/v1/metrics/runs/$runId/diff?type=code"
$delivery = Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/v1/metrics/runs/$runId/diff?type=delivery"
```

---

### 实验 1：简单层级 — 添加健康检查端点

**需求描述：**

> 给 DevFlow API 添加一个健康检查端点 GET /api/v1/health，返回 JSON 格式 {"status": "ok", "timestamp": "当前UTC时间ISO格式"}。需要在 api.py 中添加路由处理，在 OPENAPI_SPEC 中添加对应的 API 文档。

**预期阶段流转：**

| 阶段 | 预期行为 |
|------|----------|
| requirement_intake | 识别为 API 功能添加需求，结构化输出 |
| solution_design | 定位 api.py，规划添加路由+OpenAPI 文档 |
| checkpoint 1 | 方案审批（approve） |
| code_generation | 修改 api.py（添加路由+OpenAPI 条目） |
| test_generation | 生成测试代码验证 /api/v1/health 返回正确格式 |
| code_review | 审查代码正确性、安全性 |
| checkpoint 2 | 代码评审审批（approve） |
| delivery | 产出 delivery.json + delivery.diff |

**验证标准：**

| 维度 | 标准 |
|------|------|
| 产物完整性 | 6 个阶段均有对应 JSON 产物 |
| 文件变更数 | 1-2 个文件（api.py + 可能的测试文件） |
| Diff 质量 | 新增路由处理函数 + OpenAPI 条目，无无关修改 |
| 功能正确性 | GET /api/v1/health 返回 200 + {"status": "ok", "timestamp": "..."} |
| 测试覆盖 | 有对应的测试用例 |

**成功判定：**
- Pipeline 完成到 delivery 阶段（status = "delivered"）
- delivery.diff 中包含 api.py 的修改
- 修改内容与需求描述一致

**预期成功率：> 80%**

理由：单文件修改、需求明确、无跨模块依赖，代码生成 Agent 只需在 api.py 中添加一个简单的路由处理函数。

---

### 实验 2：中等层级 — 添加 Pipeline 标签功能

**需求描述：**

> 给 Pipeline 运行添加标签（Tag）功能。具体要求：1) 创建 Pipeline 时支持传入 tags 字段（字符串数组），如 ["bugfix", "v2"]；2) run.json 中保存 tags 字段；3) 列出 Pipeline 的 API（GET /api/v1/pipelines）支持按 tag 筛选，如 ?tag=bugfix；4) 在 OPENAPI_SPEC 中添加 tags 相关的参数文档。需要修改 api.py 的创建和列表处理逻辑，以及 pipeline.py 的 run_payload 结构。

**预期阶段流转：**

| 阶段 | 预期行为 |
|------|----------|
| requirement_intake | 识别为多文件功能添加需求，结构化输出含多个 user_stories |
| solution_design | 定位 api.py + pipeline.py，规划变更计划（3-5 个变更点） |
| checkpoint 1 | 方案审批（approve） |
| code_generation | 修改 api.py（创建+列表逻辑）+ pipeline.py（run_payload 结构） |
| test_generation | 生成测试验证标签创建和筛选 |
| code_review | 审查多文件变更的一致性、API 契约合规 |
| checkpoint 2 | 代码评审审批（approve） |
| delivery | 产出 delivery.json + delivery.diff |

**验证标准：**

| 维度 | 标准 |
|------|------|
| 产物完整性 | 6 个阶段均有对应 JSON 产物 |
| 文件变更数 | 3-5 个文件（api.py, pipeline.py, 可能的测试文件） |
| Diff 质量 | 创建接口添加 tags 参数、列表接口添加 tag 筛选、run_payload 添加 tags 字段 |
| 功能正确性 | 创建带 tags 的 Pipeline 后，列表接口可按 tag 筛选 |
| API 契约 | OpenAPI 文档与实际接口一致 |
| 测试覆盖 | 有标签创建和筛选的测试用例 |

**成功判定：**
- Pipeline 完成到 delivery 阶段
- delivery.diff 中包含 api.py 和 pipeline.py 的修改
- 修改内容覆盖需求的所有 4 个子要求

**预期成功率：> 50%**

理由：多文件修改、需要理解现有 API 结构和数据模型、涉及请求参数解析和查询逻辑。Agent 需要准确定位 api.py 中的创建和列表处理函数，并正确修改 pipeline.py 的 run_payload 结构。

---

### 实验 3：复杂层级 — 实现 SSE 实时推送 Pipeline 状态

**需求描述：**

> 实现 Server-Sent Events (SSE) 实时推送 Pipeline 状态变更，替代前端当前的轮询方式。具体要求：1) 添加 GET /api/v1/pipelines/{run_id}/events 端点，返回 text/event-stream 格式的 SSE 流；2) 当 Pipeline 状态变更时（阶段开始/完成、检查点等待/审批），通过 SSE 推送事件给订阅的客户端；3) 在 api.py 中添加 SSE 路由和事件推送机制；4) 在 pipeline.py 的状态变更点添加事件触发调用；5) 在 OPENAPI_SPEC 中添加 SSE 端点文档；6) 前端 dashboard 的 useRunDetail hook 可选择使用 SSE 替代轮询（可选，不强制）。

**预期阶段流转：**

| 阶段 | 预期行为 |
|------|----------|
| requirement_intake | 识别为架构级功能需求，结构化输出含多个高优先级 user_stories |
| solution_design | 分析现有 HTTP 服务器架构限制，设计 SSE 推送机制（可能需要引入 threading.Event 或消息队列），规划 5+ 个变更点 |
| checkpoint 1 | 方案审批（approve，可能需要人工评审架构方案） |
| code_generation | 修改 api.py（SSE 路由+事件格式）+ pipeline.py（状态变更触发）+ 可能新增 sse.py 模块 |
| test_generation | 生成 SSE 连接测试、事件推送测试 |
| code_review | 审查架构合理性、SSE 连接管理、内存泄漏风险、线程安全 |
| checkpoint 2 | 代码评审审批（approve） |
| delivery | 产出 delivery.json + delivery.diff |

**验证标准：**

| 维度 | 标准 |
|------|------|
| 产物完整性 | 6 个阶段均有对应 JSON 产物 |
| 文件变更数 | 5+ 个文件（api.py, pipeline.py, 新模块, 配置, 前端 hook） |
| Diff 质量 | 新增 SSE 端点、事件推送机制、状态变更触发点、OpenAPI 文档 |
| 功能正确性 | SSE 端点返回 text/event-stream，状态变更时推送事件 |
| 架构合理性 | SSE 连接管理（超时、断开、内存释放）处理得当 |
| 线程安全 | 多客户端并发订阅时无竞态条件 |
| 测试覆盖 | 有 SSE 连接和事件推送的测试 |

**成功判定：**
- Pipeline 完成到 delivery 阶段
- delivery.diff 中包含 SSE 相关的新增代码
- 代码变更覆盖需求的核心子要求（SSE 端点 + 状态变更推送）

**预期成功率：> 20%**

理由：架构级功能、需要理解现有 stdlib HTTPServer 的局限性、涉及新模块设计、跨层集成（API 层 + Pipeline 层 + 前端层）、线程安全考量。Agent 需要做出多个架构决策，且 stdlib HTTPServer 对 SSE 的支持不如异步框架自然。

---

## 三、结果记录模板

每个实验完成后，记录以下信息：

```json
{
  "experiment_level": "simple|medium|complex",
  "experiment_name": "实验名称",
  "run_id": "运行 ID",
  "timestamp": "实验时间",
  "provider": "使用的 LLM Provider",
  "model": "使用的模型",
  "result": {
    "final_status": "delivered|failed|terminated",
    "stages_completed": ["requirement_intake", "solution_design", "..."],
    "stages_failed": [],
    "checkpoints": [
      {"stage": "solution_design", "decision": "approve", "attempt": 1},
      {"stage": "code_review", "decision": "approve", "attempt": 1}
    ],
    "files_changed": 0,
    "lines_added": 0,
    "lines_removed": 0
  },
  "quality": {
    "requirement_coverage": "需求覆盖度评估（1-5）",
    "code_correctness": "代码正确性评估（1-5）",
    "test_adequacy": "测试充分性评估（1-5）",
    "architecture_fit": "架构适配性评估（1-5）"
  },
  "metrics": {
    "total_duration_seconds": 0,
    "token_usage": {},
    "stage_durations": {}
  },
  "notes": "人工评审备注"
}
```

---

## 四、对本项目验证策略的启示

### 4.1 从行业实践得出的关键结论

1. **端到端验证不可省略**：SWE-bench 证明单函数基准（HumanEval）不足以衡量工程能力。DevFlow 必须验证从需求到交付的完整链路。
2. **编排正确性 ≠ 输出质量**：Pipeline 按预期流转（6 阶段全部 success）只是必要条件，最终代码是否可用才是充分条件。
3. **分级任务集是行业标准**：MetaGPT/ChatDev/Devin 都使用分级任务集，从简单到复杂逐步验证。
4. **评估器需要分层**：代码用测试执行评判，方案用人工评审，交付用 Schema 校验。

### 4.2 对现场命题挑战的应对策略

1. **提前跑通三级实验**：建立基线结果，了解系统在不同复杂度下的表现边界。
2. **简单实验作为保底**：如果现场命题偏简单，确保 > 80% 成功率。
3. **中等实验展示差异化**：多文件功能添加是 DevFlow 最能展示价值的场景。
4. **复杂实验展示上限**：即使成功率不高，也能展示系统的架构理解能力。
5. **准备 Reject 场景**：现场演示时主动展示一次 Reject + 重做，证明 Human-in-the-Loop 机制有效。

### 4.3 Seedance Code 2.0 适配建议

- 在三个实验中分别使用 Seedance Code 2.0 作为 Provider
- 记录各阶段的 token 消耗和响应延迟，与 baseline Provider 对比
- 重点关注代码生成和测试生成阶段的表现（这两个阶段对代码能力要求最高）
- 如果 Seedance Code 2.0 在某些阶段表现不佳，可通过 API 的 `provider` 参数在不同阶段使用不同 Provider
