# Pipeline 执行监控面板重构 Spec

## Why

当前仪表板是一个通用的可观测性面板，聚焦于聚合指标（总运行数、成功率、Token 趋势），无法让用户直观感知 AI Agent 的推理过程、中间产物和审批决策。参考 Trae SOLO 的核心理念——**Responsive Review（实时可见每一步决策）、Responsive Context（上下文始终可见）、Plan before Execute（先规划再执行）**——本 Spec 将仪表板从"事后统计面板"重构为"Pipeline 执行监控面板"，以单次运行为核心，实时展示当前阶段、进度、耗时、Token 消耗、LLM 推理中间过程、中间文档、审批操作和最终交付成果。

## What Changes

- **重构前端页面布局**：从"KPI + 图表 + 列表"的聚合视图，改为以单次 Pipeline 运行为核心的执行监控视图
- **新增 LLM 推理过程展示**：读取 `llm-request.json` 和 `llm-response.json`，展示 System Prompt 摘要、User Prompt 摘要、模型输出内容、reasoning_tokens（如有）
- **新增中间产物展示**：读取各阶段 artifact JSON（`requirement.json`、`solution.json`、`code-generation.json`、`test-generation.json`、`code-review.json`、`delivery.json`），以结构化卡片展示关键信息
- **新增审批时间线**：读取 `checkpoint.json`，展示审批状态、决策人、决策时间、拒绝理由
- **新增活跃运行自动聚焦**：API 端点返回当前活跃运行，前端自动聚焦到活跃运行
- **新增后端数据端点**：提供运行详情、LLM 推理链、产物列表、审批历史的聚合 API
- **移除原有聚合图表**：移除 StageStatsChart、RunsTrendChart、TokenUsageChart 等聚合图表组件，保留 RecentRunsTable 作为侧边栏运行选择器

## Impact

- Affected specs: `build-observability-dashboard` 的前端组件和 API 端点
- Affected code: `dashboard/src/` 下几乎所有组件需重写；`devflow/metrics.py` 新增函数；`devflow/api.py` 新增端点
- 无 Breaking Changes，原有 API 端点保留但前端不再使用
- 前端组件大幅精简，移除 Recharts 依赖

## 设计理念（参考 Trae SOLO）

| Trae SOLO 理念 | 本面板映射 |
|---|---|
| Responsive Review — 实时可见每一步决策 | Pipeline Stepper + 阶段详情面板，实时展示当前阶段状态和 Agent 行为 |
| Responsive Context — 上下文始终可见 | LLM 推理面板展示 System Prompt / User Prompt / 模型输出，让用户理解 Agent 的上下文 |
| Plan before Execute — 先规划再执行 | 方案设计阶段的产物（solution.json / solution.md）以结构化卡片展示，审批前可预览 |
| Visual Workspace — 编辑器/终端/浏览器一体化 | 阶段详情面板集成：产物卡片、LLM 推理、审批操作、代码 Diff 预览 |
| Ship in parallel — 多任务并行可见 | 侧边栏运行列表支持快速切换不同运行 |

## ADDED Requirements

### Requirement: Pipeline 执行监控主视图

The system SHALL 提供以单次 Pipeline 运行为核心的执行监控主视图，取代原有的聚合指标视图。

#### Scenario: 页面布局
- **WHEN** 用户打开 `/dashboard`
- **THEN** 页面分为三个区域：
  - **左侧栏（240px）**：运行列表，展示最近运行，当前活跃运行高亮，点击切换
  - **中央区**：Pipeline 执行监控主面板
  - **右侧栏（可折叠，默认 360px）**：LLM 推理详情面板

#### Scenario: 自动聚焦活跃运行
- **WHEN** 存在 status 为 `running` 或 `paused` 的运行
- **THEN** 前端自动选中并展示该运行
- **WHEN** 无活跃运行
- **THEN** 前端默认展示最近一次运行

#### Scenario: 无运行数据
- **WHEN** 系统中无任何运行记录
- **THEN** 显示引导空状态："启动 DevFlow 后，Pipeline 运行将在此处实时展示"

### Requirement: Pipeline Stepper 组件

The system SHALL 在中央区顶部展示水平 Pipeline Stepper，可视化各阶段状态。

#### Scenario: Stepper 展示
- **WHEN** 选中一个运行
- **THEN** 展示 6 个阶段的水平 Stepper：需求分析 → 方案设计 → 代码生成 → 测试生成 → 代码评审 → 交付
- **THEN** 每个阶段节点显示：
  - 阶段图标和名称
  - 状态指示（pending / running / success / failed / blocked）
  - running 状态有脉冲动画
  - success 状态显示耗时
  - failed 状态显示错误标记
  - blocked 状态显示等待审批标记
- **THEN** 阶段间用连接线连接，已完成阶段连接线为实线，未完成为虚线

#### Scenario: 阶段点击
- **WHEN** 用户点击某个阶段节点
- **THEN** 中央区下方滚动到该阶段的详情面板

### Requirement: 阶段详情面板

The system SHALL 在 Stepper 下方展示当前选中阶段的详情面板，包含进度、耗时、Token、产物等信息。

#### Scenario: 阶段概览卡片
- **WHEN** 展示某个阶段的详情
- **THEN** 显示以下信息行：
  - **状态**：Badge 标签（running / success / failed / blocked / pending）
  - **耗时**：已消耗时间（running 时实时更新，格式如 `2m 15s`）
  - **Token 消耗**：prompt_tokens / completion_tokens / total_tokens（如有）
  - **Provider**：使用的 LLM Provider

#### Scenario: 阶段产物卡片
- **WHEN** 该阶段已产出 artifact 文件
- **THEN** 以可展开卡片展示产物摘要：
  - **需求分析**：需求标题、验收标准数量、质量评分
  - **方案设计**：方案摘要、变更文件数、风险等级、质量就绪状态
  - **代码生成**：变更文件列表、Diff 统计（+行/-行）
  - **测试生成**：检测到的测试框架、生成测试数、执行结果
  - **代码评审**：评审状态、阻塞问题数、风险等级
  - **交付**：变更摘要、Git 状态、合并就绪状态
- **THEN** 每个产物卡片有"查看详情"按钮，点击在右侧 LLM 面板展示完整 JSON

#### Scenario: 代码 Diff 预览
- **WHEN** 代码生成或测试生成阶段有 `.diff` 文件
- **THEN** 在产物卡片下方展示 Diff 预览区域，以语法高亮显示变更内容
- **THEN** Diff 区域默认折叠，显示前 20 行，可展开查看完整内容

### Requirement: LLM 推理详情面板

The system SHALL 在右侧栏展示 LLM 推理过程的详细信息，让用户理解 AI Agent 的思考过程。

#### Scenario: 推理链展示
- **WHEN** 当前阶段有 LLM 调用记录（`*-llm-request.json` / `*-llm-response.json`）
- **THEN** 展示以下信息：
  - **System Prompt 摘要**：截取前 200 字，可展开查看完整内容
  - **User Prompt 摘要**：截取前 200 字，可展开查看完整内容
  - **模型输出**：展示 LLM 返回的 content，支持 JSON 格式化显示
  - **Token 统计**：prompt_tokens / completion_tokens / total_tokens
  - **调用耗时**：duration_ms
  - **Provider / Model**：使用的模型信息

#### Scenario: 多次 LLM 调用
- **WHEN** 同一阶段有多次 LLM 调用（如代码生成 Agent 的工具循环）
- **THEN** 以时间线形式展示每次调用的摘要，点击展开详情
- **THEN** 每次调用显示：调用序号、耗时、Token 数、输出摘要

#### Scenario: 无 LLM 调用
- **WHEN** 当前阶段无 LLM 调用记录
- **THEN** 显示"本阶段无 LLM 调用"

### Requirement: 审批时间线

The system SHALL 在阶段详情面板中展示人工审批操作的时间线。

#### Scenario: 审批记录展示
- **WHEN** 运行有 checkpoint.json 记录
- **THEN** 在对应阶段（方案设计 / 代码评审）的详情面板中展示审批卡片：
  - **审批状态**：waiting_approval / approved / rejected / approved_with_override
  - **审批阶段**：solution_design / code_review
  - **决策人**：reviewer 信息
  - **决策时间**：updated_at
  - **拒绝理由**：reject_reason（如有）
  - **质量快照**：quality_snapshot（如有）
  - **强制通过标记**：override_reason（如有）

#### Scenario: 审批等待状态
- **WHEN** 当前阶段处于 waiting_approval 状态
- **THEN** 审批卡片以醒目的橙色边框展示，显示"等待审批"
- **THEN** 提供 API 端点链接提示："可通过 API 审批：POST /api/v1/pipelines/{run_id}/checkpoint"

### Requirement: 交付成果展示

The system SHALL 在交付阶段展示最终交付成果。

#### Scenario: 交付成果展示
- **WHEN** 运行已完成交付阶段
- **THEN** 在交付阶段详情面板展示：
  - **变更摘要**：delivery.json 中的 change_summary
  - **验证证据**：verification_evidence
  - **Git 状态**：branch / HEAD / tracked diff stats
  - **合并就绪**：merge_readiness 状态
  - **Diff 预览**：delivery.diff 内容

### Requirement: 运行列表侧边栏

The system SHALL 在左侧栏展示运行列表，替代原有的 RecentRunsTable。

#### Scenario: 运行列表展示
- **WHEN** 用户打开仪表板
- **THEN** 左侧栏展示最近 20 次运行，每行显示：
  - 运行 ID（截断显示）
  - 状态 Badge
  - 当前阶段
  - 启动时间
- **THEN** 当前选中运行高亮
- **THEN** 活跃运行（running/paused）有脉冲动画指示

#### Scenario: 运行切换
- **WHEN** 用户点击侧边栏中的某个运行
- **THEN** 中央区和右侧栏切换到该运行的详情

### Requirement: 新增后端 API 端点

The system SHALL 提供以下新 API 端点，供前端获取运行详情数据。

#### Scenario: 获取活跃运行
- **WHEN** 前端请求 `GET /api/v1/metrics/active-run`
- **THEN** 返回当前 status 为 running 或 paused 的运行（如有多个返回最新的），无活跃运行返回 `null`

#### Scenario: 获取运行完整详情
- **WHEN** 前端请求 `GET /api/v1/metrics/runs/{run_id}/detail`
- **THEN** 返回该运行的完整信息，包含：
  - `run`：run.json 完整内容
  - `stages`：每个阶段的详细信息（status, started_at, ended_at, duration_ms）
  - `artifacts`：每个阶段产物的摘要信息
  - `checkpoints`：审批记录列表
  - `llm_calls`：LLM 调用记录列表
  - `token_summary`：Token 消耗汇总
  - `delivery`：交付信息（如有）

#### Scenario: 获取运行 LLM 推理链
- **WHEN** 前端请求 `GET /api/v1/metrics/runs/{run_id}/llm-trace`
- **THEN** 返回该运行所有 LLM 调用的详细信息：
  - 每次调用的 stage、request 摘要、response 摘要、usage、duration_ms
  - request 中提取 system_prompt 和 user_prompt 的前 500 字
  - response 中提取 content 的前 1000 字

#### Scenario: 获取运行产物列表
- **WHEN** 前端请求 `GET /api/v1/metrics/runs/{run_id}/artifacts`
- **THEN** 返回该运行各阶段产物的结构化摘要

#### Scenario: 获取 Diff 内容
- **WHEN** 前端请求 `GET /api/v1/metrics/runs/{run_id}/diff?type={stage}`
- **THEN** 返回指定阶段的 diff 文件内容（code-generation.diff / test-generation.diff / delivery.diff）
- **THEN** type 参数支持：code / test / delivery

### Requirement: 实时刷新与进度追踪

The system SHALL 支持运行状态的实时刷新和进度追踪。

#### Scenario: 自动刷新
- **WHEN** 当前选中的运行为 running 状态
- **THEN** 每 3 秒自动轮询 `GET /api/v1/metrics/runs/{run_id}/detail`
- **WHEN** 当前选中的运行为非 running 状态
- **THEN** 每 10 秒轮询一次

#### Scenario: 运行耗时实时更新
- **WHEN** 当前阶段为 running 状态
- **THEN** 前端基于 started_at 时间戳，每秒更新已消耗时间的显示

## MODIFIED Requirements

### Requirement: 前端依赖调整
- 移除 `recharts` 依赖（不再需要聚合图表）
- 保留 `react`、`react-dom`、`lucide-react`、`@radix-ui/*`、`class-variance-authority`、`clsx`、`tailwind-merge`
- 新增 `react-diff-viewer-continued` 用于 Diff 预览（或使用自定义 Diff 渲染）

### Requirement: API 路由注册
- `api.py` 中的 `_ROUTE_PATTERNS` 和 `_dispatch` 方法新增端点：
  - `GET /api/v1/metrics/active-run`
  - `GET /api/v1/metrics/runs/{run_id}/detail`
  - `GET /api/v1/metrics/runs/{run_id}/llm-trace`
  - `GET /api/v1/metrics/runs/{run_id}/artifacts`
  - `GET /api/v1/metrics/runs/{run_id}/diff`

### Requirement: metrics.py 扩展
- 新增 `get_active_run(out_dir)` 函数
- 新增 `get_run_detail(run_dir)` 函数
- 新增 `get_run_llm_trace(run_dir)` 函数
- 新增 `get_run_artifacts(run_dir)` 函数
- 新增 `get_run_diff(run_dir, stage)` 函数

## REMOVED Requirements

### Requirement: 聚合图表组件
**Reason**: 重构为执行监控面板后，聚合指标不再是核心关注点
**Migration**: 保留原有 API 端点（`/api/v1/metrics/overview`、`/stage-stats`、`/token-usage`）供外部调用，但前端不再使用。移除以下组件：
- `StageStatsChart.tsx`
- `RunsTrendChart.tsx`
- `TokenUsageChart.tsx`
- `KpiCards.tsx`

### Requirement: RunDetailDialog 弹窗
**Reason**: 执行监控面板以单次运行为核心视图，不再需要弹窗查看详情
**Migration**: 原有弹窗功能合并到主视图的阶段详情面板中
