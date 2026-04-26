# DevFlow Engine MVP Spec

## Why

DevFlow Engine 需要从零实现一个 AI 驱动的需求到代码交付管道，证明 AI 可以稳定编排从自然语言需求到可交付 patch 的完整研发流程闭环。当前仓库仅有目录骨架和设计文档，所有代码文件为空，需要完整实现 MVP。

## What Changes

- 创建后端 Python 项目基础设施（pyproject.toml、`__init__.py` 包结构、FastAPI 入口）
- 创建前端 React 项目基础设施（Vite + TypeScript + React）
- 实现 SQLite 数据库层（SQLAlchemy models、连接管理、表初始化）
- 实现 Pipeline 状态机（PipelineRun 和 StageRun 的状态转换逻辑）
- 实现 Pipeline Orchestrator（流程编排、阶段推进、checkpoint 暂停/恢复）
- 实现 Artifact Store（结构化产物存储、小 JSON 存 SQLite、大文本存文件系统）
- 实现 Checkpoint Service（人工审批、Approve/Reject、回退机制）
- 实现 Workspace Manager（隔离工作区创建、Git 仓库注册与克隆）
- 实现 Patch Applier（patch 生成、应用、diff 生成）
- 实现 Command Runner（测试命令执行、stdout/stderr 捕获）
- 实现 Provider Registry（LLM Provider 注册、Mock/OpenAI-compatible/Anthropic 适配器）
- 实现 6 个 Agent（requirement、design、code_patch、test、review、delivery）及 Mock Agent
- 实现 5 组 REST API 端点（Pipeline、Checkpoint、Artifact、Workspace、Provider）
- 实现前端控制台（Pipeline 列表、详情时间线、Checkpoint 审批、Diff 查看器）
- 实现完整端到端演示（自举：为自身添加 health 接口）

## Impact

- Affected specs: 全部 MVP 功能
- Affected code: backend/app/ 下所有模块、frontend/src/ 下所有模块

## ADDED Requirements

### Requirement: 项目基础设施

系统 SHALL 提供可运行的后端和前端项目骨架。

#### Scenario: 后端可启动
- **WHEN** 执行 `uv run uvicorn app.main:app --reload`
- **THEN** FastAPI 服务启动成功，`/docs` 可访问 Swagger UI，`/api/health` 返回 200

#### Scenario: 前端可启动
- **WHEN** 执行 `npm run dev`
- **THEN** Vite 开发服务器启动成功，浏览器可访问前端页面

### Requirement: 数据库层

系统 SHALL 使用 SQLite 作为元数据存储，SQLAlchemy 作为 ORM。

#### Scenario: 表自动创建
- **WHEN** FastAPI 应用启动
- **THEN** 自动创建 pipeline_run、stage_run、artifact、checkpoint_record、workspace、provider_config 表

#### Scenario: 数据持久化
- **WHEN** 创建 PipelineRun 记录
- **THEN** 记录持久化到 SQLite，重启后可查询

### Requirement: Pipeline 状态机

系统 SHALL 实现 PipelineRun 的 8 种状态和 StageRun 的 6 种状态及其合法转换。

#### Scenario: PipelineRun 正常流转
- **WHEN** 创建 PipelineRun
- **THEN** 初始状态为 `draft`
- **WHEN** 预检通过
- **THEN** 状态转为 `ready`
- **WHEN** 用户启动
- **THEN** 状态转为 `running`
- **WHEN** 遇到 checkpoint 阶段
- **THEN** 状态转为 `waiting_checkpoint`
- **WHEN** 用户 Approve
- **THEN** 状态转为 `running`，推进到下一阶段
- **WHEN** 全部阶段完成
- **THEN** 状态转为 `succeeded`

#### Scenario: PipelineRun 异常流转
- **WHEN** 阶段执行失败且重试耗尽
- **THEN** 状态转为 `failed`
- **WHEN** 用户终止
- **THEN** 状态转为 `terminated`

#### Scenario: StageRun 状态流转
- **WHEN** 阶段开始执行
- **THEN** 状态从 `pending` 转为 `running`
- **WHEN** 阶段执行成功
- **THEN** 状态转为 `succeeded`
- **WHEN** 阶段执行失败
- **THEN** 状态转为 `failed`，可进入 `retrying`

### Requirement: Pipeline Orchestrator

系统 SHALL 编排 8 个阶段的线性 Pipeline 执行。

#### Scenario: 默认模板加载
- **WHEN** 系统启动
- **THEN** 加载 `feature_delivery_default` 模板，包含 8 个阶段定义

#### Scenario: 阶段顺序推进
- **WHEN** 当前阶段执行成功
- **THEN** 自动推进到下一阶段
- **WHEN** 当前阶段为 checkpoint 类型
- **THEN** 暂停执行，等待人工审批

#### Scenario: Reject 回退
- **WHEN** checkpoint_design_approval 被 Reject
- **THEN** 回退到 solution_design 阶段，Reject reason 注入上下文
- **WHEN** checkpoint_final_approval 被 Reject
- **THEN** 回退到 code_generation 阶段

### Requirement: Artifact Store

系统 SHALL 为每个阶段保存结构化产物，支持小 JSON 存 SQLite、大文本存文件系统。

#### Scenario: 小 JSON 产物存储
- **WHEN** 阶段产出 < 10KB 的 JSON
- **THEN** 直接存入 SQLite 的 content 字段

#### Scenario: 大文本产物存储
- **WHEN** 阶段产出 >= 10KB
- **THEN** 存入文件系统 `artifacts/{run_id}/stage_{stage_key}/` 目录，URI 引用存入 SQLite

#### Scenario: 产物查询
- **WHEN** 通过 API 查询 Artifact
- **THEN** 返回结构化 JSON，大文本自动从文件系统读取

### Requirement: Artifact Schema 校验

系统 SHALL 对每种 Artifact 类型进行 Schema 校验。

#### Scenario: requirement_brief 校验
- **WHEN** requirement_analysis 阶段产出 requirement_brief
- **THEN** 必须包含 goal、acceptance_criteria、constraints、assumptions、risks 字段

#### Scenario: design_spec 校验
- **WHEN** solution_design 阶段产出 design_spec
- **THEN** 必须包含 summary、affected_files、test_strategy 字段

#### Scenario: change_set 校验
- **WHEN** code_generation 阶段产出 change_set
- **THEN** 必须包含 files 数组，每个 file 包含 path、change_type、patch

#### Scenario: test_report 校验
- **WHEN** test_generation_and_execution 阶段产出 test_report
- **THEN** 必须包含 exit_code、stdout、stderr、duration_ms 字段

#### Scenario: review_report 校验
- **WHEN** code_review 阶段产出 review_report
- **THEN** 必须包含 recommendation、scores、issues、summary 字段

#### Scenario: delivery_summary 校验
- **WHEN** delivery_integration 阶段产出 delivery_summary
- **THEN** 必须包含 status、deliverables、test_summary、known_risks、next_steps 字段

### Requirement: Checkpoint Service

系统 SHALL 实现人工检查点的审批流程。

#### Scenario: Checkpoint 创建
- **WHEN** Pipeline 执行到 checkpoint 阶段
- **THEN** 创建 CheckpointRecord，status=pending，PipelineRun 进入 waiting_checkpoint

#### Scenario: Approve 审批
- **WHEN** 用户提交 Approve
- **THEN** CheckpointRecord status=approved，PipelineRun 恢复 running，跳转到 approve_target

#### Scenario: Reject 审批
- **WHEN** 用户提交 Reject 并携带 reason
- **THEN** CheckpointRecord status=rejected，reason 被保存，PipelineRun 恢复 running，跳转到 reject_target

#### Scenario: Reject reason 可读取
- **WHEN** 回退阶段重新执行
- **THEN** Agent 可读取上一次 Reject reason 作为输入

### Requirement: Workspace Manager

系统 SHALL 管理隔离的 Git 工作区。

#### Scenario: 仓库注册
- **WHEN** 用户注册本机 Git 仓库路径
- **THEN** 系统验证路径存在且为 Git 仓库，创建 Workspace 记录

#### Scenario: 隔离 workspace 创建
- **WHEN** PipelineRun 启动
- **THEN** 从 source_repo_path 克隆到独立 workspace_path，记录 git_commit_at_create

#### Scenario: Workspace 隔离保证
- **WHEN** Agent 在 workspace 中执行代码变更
- **THEN** 变更仅发生在隔离目录，不影响 source_repo_path

### Requirement: Patch Applier

系统 SHALL 支持 patch 的生成、应用和 diff 展示。

#### Scenario: Patch 应用
- **WHEN** Agent 生成 unified diff 格式的 patch
- **THEN** 系统在隔离 workspace 中 apply patch，记录 apply 结果

#### Scenario: Patch 应用失败重试
- **WHEN** patch apply 失败
- **THEN** 最多重试 2 次

#### Scenario: Diff 生成
- **WHEN** patch apply 成功
- **THEN** 系统生成 diff_manifest，包含 base_commit、changed_files、stats

### Requirement: Command Runner

系统 SHALL 执行测试命令并捕获结果。

#### Scenario: 测试命令执行
- **WHEN** 执行测试命令
- **THEN** 捕获 stdout、stderr、exit_code、duration_ms

#### Scenario: 测试失败不阻塞
- **WHEN** 测试命令 exit_code != 0
- **THEN** 记录 test_report，Pipeline 不终止，继续后续阶段

### Requirement: Provider Registry

系统 SHALL 支持 LLM Provider 的注册、配置和运行时切换。

#### Scenario: Mock Provider
- **WHEN** 使用 mock provider
- **THEN** 返回预定义的固定输出，用于测试和 Mock Agent 闭环

#### Scenario: OpenAI-compatible Provider
- **WHEN** 配置 OpenAI-compatible provider
- **THEN** 支持 api_base、api_key、model 配置，支持 structured output

#### Scenario: Anthropic Provider
- **WHEN** 配置 Anthropic provider
- **THEN** 支持 api_key、model 配置，支持 structured output

#### Scenario: Provider 验证
- **WHEN** 用户调用 validate API
- **THEN** 验证 provider 连通性和认证有效性

#### Scenario: Provider 切换
- **WHEN** PipelineRun 指定 provider_selection_override
- **THEN** 使用指定的 provider 而非默认 provider

### Requirement: Agent 实现

系统 SHALL 实现 6 个 Agent 和 Mock Agent 支持。

#### Scenario: Mock Agent 闭环
- **WHEN** 使用 Mock Agent 运行 Pipeline
- **THEN** 所有阶段使用固定输出，完整跑通 8 个阶段，不依赖 LLM

#### Scenario: Requirement Agent
- **WHEN** 输入自然语言需求
- **THEN** 输出结构化 requirement_brief（goal、acceptance_criteria、constraints、assumptions、risks）

#### Scenario: Design Agent
- **WHEN** 输入 requirement_brief 和代码库上下文
- **THEN** 输出 design_spec（summary、affected_files、test_strategy、risks）

#### Scenario: Code Patch Agent
- **WHEN** 输入 design_spec 和代码上下文
- **THEN** 输出 change_set（files 数组，每个包含 path、change_type、patch）

#### Scenario: Test Agent
- **WHEN** 输入 change_set 和 requirement_brief
- **THEN** 输出 test_report（exit_code、stdout、stderr、duration_ms、summary）

#### Scenario: Review Agent
- **WHEN** 输入 design_spec、change_set、test_report
- **THEN** 输出 review_report（recommendation、scores、issues、summary）

#### Scenario: Delivery Agent
- **WHEN** 输入已批准的 change_set、review_report、test_report
- **THEN** 输出 delivery_summary（status、deliverables、test_summary、known_risks、next_steps）

### Requirement: REST API

系统 SHALL 通过 RESTful API 暴露所有核心操作。

#### Scenario: Pipeline 管理 API
- **WHEN** 调用 `POST /api/pipelines`
- **THEN** 创建 PipelineRun，返回完整对象
- **WHEN** 调用 `POST /api/pipelines/{id}/start`
- **THEN** 启动 Pipeline，状态从 ready 转为 running
- **WHEN** 调用 `GET /api/pipelines/{id}/timeline`
- **THEN** 返回各阶段执行状态时间线

#### Scenario: Checkpoint API
- **WHEN** 调用 `POST /api/checkpoints/{id}/approve`
- **THEN** 审批通过，Pipeline 继续
- **WHEN** 调用 `POST /api/checkpoints/{id}/reject`
- **THEN** 审批拒绝，Pipeline 回退

#### Scenario: Artifact API
- **WHEN** 调用 `GET /api/artifacts/{id}`
- **THEN** 返回结构化产物
- **WHEN** 调用 `GET /api/pipelines/{id}/artifacts`
- **THEN** 返回该 Run 的所有产物

#### Scenario: Workspace API
- **WHEN** 调用 `POST /api/workspaces`
- **THEN** 注册 Git 仓库
- **WHEN** 调用 `GET /api/workspaces/{id}/diff`
- **THEN** 返回代码变更 diff

#### Scenario: Provider API
- **WHEN** 调用 `POST /api/providers`
- **THEN** 创建 Provider 配置
- **WHEN** 调用 `POST /api/providers/{id}/validate`
- **THEN** 验证 Provider 连通性

### Requirement: 前端控制台

系统 SHALL 提供最小 React 前端控制台。

#### Scenario: Pipeline 列表页
- **WHEN** 访问前端首页
- **THEN** 显示所有 PipelineRun 列表，支持状态筛选

#### Scenario: Pipeline 详情页
- **WHEN** 点击某个 PipelineRun
- **THEN** 显示时间线视图，展示各阶段状态和产物

#### Scenario: Checkpoint 审批 UI
- **WHEN** Pipeline 处于 waiting_checkpoint 状态
- **THEN** 显示审批面板，展示 requirement_brief 和 design_spec（或 change_set 和 review_report），支持 Approve/Reject 操作

#### Scenario: Diff 查看器
- **WHEN** 查看代码变更
- **THEN** 显示 unified diff 格式的代码对比

### Requirement: 端到端演示

系统 SHALL 支持一次完整的自举演示。

#### Scenario: 自举演示
- **WHEN** 输入需求"为 DevFlow Engine 增加 GET /api/health 接口"
- **THEN** Pipeline 完整跑通 8 个阶段，产出可运行的代码变更
- **THEN** 变更包含 health 接口实现和测试
- **THEN** 测试通过

### Requirement: 错误处理

系统 SHALL 对不同类型错误采用不同处理策略。

#### Scenario: 输入错误
- **WHEN** API 参数校验失败
- **THEN** 返回 400，不创建 Run

#### Scenario: 预检错误
- **WHEN** 仓库路径不存在
- **THEN** Run 状态保持 draft，返回错误详情

#### Scenario: 执行错误
- **WHEN** Agent 执行失败
- **THEN** StageRun 标记 failed，触发重试或终止

#### Scenario: 系统错误
- **WHEN** 数据库或文件系统错误
- **THEN** 记录日志，返回 500

### Requirement: 安全设计

系统 SHALL 保证代码变更安全。

#### Scenario: Agent 不直接修改原始仓库
- **WHEN** Agent 生成代码变更
- **THEN** 变更仅发生在隔离 workspace，Agent 不直接写入 source_repo_path

#### Scenario: API Key 加密存储
- **WHEN** 保存 Provider 的 API Key
- **THEN** API Key 加密后存储，不以明文保存
