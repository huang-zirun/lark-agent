# DevFlow Engine Design Snapshot

---

## 1. 项目目标

为飞书 AI 校园挑战赛构建 DevFlow Engine，一个 AI 驱动的需求到代码交付管道。

MVP 证明一个核心能力：DevFlow Engine 能够可靠地编排从自然语言需求到可审查代码补丁的完整 AI 软件交付循环。

主流程：需求输入 → 需求分析 → 方案设计 → 人工审批 → 代码补丁生成 → 测试执行 → 代码审查 → 最终人工审批 → 交付总结

---

## 2. 设计原则

### 2.1 MVP 优先

第一目标是完成 must-have 闭环和端到端演示，而不是提前实现完整平台能力。MVP 只证明一件事：DevFlow Engine 可以稳定编排一次从需求到可交付 patch 的研发流程。

### 2.2 先骨架，后智能

第一阶段先使用 Mock Agent 跑通完整流程，再接入真实 LLM Provider。不得让模型不稳定性阻塞 Pipeline、状态机、Artifact、Checkpoint、Workspace 等核心工程骨架。

### 2.3 契约优先

所有关键阶段产物必须有结构化 Schema，不允许阶段之间依赖自由文本猜测。每个 Agent 必须明确输入 Schema、输出 Schema、可用工具、Provider、重试策略以及失败处理方式。

### 2.4 人类监督关键节点

Pipeline 中至少有两个强制检查点：方案设计审批和最终评审确认。检查点必须支持 Approve（继续流程）、Reject（携带理由回退）、记录决策，以及后续阶段能读取 Reject 理由。

### 2.5 安全执行

Agent 不直接任意修改真实仓库。所有代码变更必须发生在隔离 workspace 中。Agent 只生成 patch 或变更计划，系统工具负责 apply patch、生成 diff、执行测试。

### 2.6 Windows 原生优先

本项目默认运行环境是 Windows 原生环境，同时保证 Docker 兼容。所有路径、命令执行、编码、换行符和文件锁行为都必须显式考虑 Windows。

---

## 3. MVP 范围

### 3.1 必须实现

必须实现的功能包括：FastAPI 后端服务、OpenAPI / Swagger 文档、SQLite 元数据存储、文件系统 Artifact Store、默认 Pipeline Template、Pipeline Run 状态机、StageRun 执行记录、两个人工检查点、Approve / Reject / 回退机制、Mock Agent 完整闭环、至少 2 个 LLM Provider 适配器（OpenAI-compatible 和 Anthropic）、本机 Git 仓库注册与预检、隔离 workspace 创建、Patch 生成应用与 diff 展示、测试命令执行与 test_report 保存、review_report 与 delivery_summary 生成、最小 React 前端控制台，以及一次完整自举演示。

### 3.2 当前不做

当前不实现的功能包括：浏览器注入式 Agent、页面圈选修改、实时热更新、自动 MR/PR 创建、分布式 Worker、消息队列、微服务拆分、多租户权限模型、企业级审计合规、复杂语义代码索引、向量数据库、多 Agent 协商、任意复杂 DAG Pipeline、远程仓库自动操作。

### 3.3 保留扩展位

为未来保留的扩展能力包括：Bugfix / Refactor / Feature 多模板、多 Agent 并行、自动回归修复、最大重试控制、代码语义索引、Git 分支 commit PR/MR 集成、可观测性大盘、长任务恢复执行。

---

## 4. MVP 总体架构

采用模块化单体架构。

```
React Console / Swagger UI
          |
          v
      FastAPI API Layer
          |
          v
+----------------------------+
|    Pipeline Orchestrator   |
+----------------------------+
   |          |          |
   v          v          v
Executor   Checkpoint   Artifact
Runtime    Service      Service
   |                      |
   v                      v
Provider Registry     SQLite + File Store
   |
   v
Workspace Manager
   |
   v
Isolated Git Workspace
```

### 4.1 模块划分

```
backend/
  app/
    api/
      routes_pipeline.py
      routes_checkpoint.py
      routes_artifact.py
      routes_workspace.py
      routes_provider.py

    core/
      orchestrator.py
      executor.py
      checkpoint_service.py
      artifact_service.py
      workspace_manager.py
      provider_registry.py
      schema_validator.py
      patch_applier.py
      command_runner.py

    agents/
      requirement_agent.py
      design_agent.py
      code_patch_agent.py
      test_agent.py
      review_agent.py
      delivery_agent.py
      mock_agents.py

    models/
      pipeline.py
      stage.py
      artifact.py
      checkpoint.py
      workspace.py
      provider.py

    db/
      connection.py
      migrations/

    schemas/
      pipeline_schemas.py
      artifact_schemas.py

  tests/

frontend/
  src/
    components/
    pages/
    api/
    store/
```

---

## 5. 默认 Pipeline 模板

### 5.1 MVP 模板策略

引擎层保留 PipelineTemplate 与 StageDefinition 概念。但 MVP 第一版只支持一条默认线性模板：feature_delivery_default。第一版不实现任意复杂 DAG，只支持线性阶段依赖。后续新增 Bugfix、Refactor 等流程时，应优先新增模板数据，而不是修改编排器主逻辑。

### 5.2 默认阶段链路

默认阶段链路包含 8 个阶段：requirement_analysis、solution_design、checkpoint_design_approval、code_generation、test_generation_and_execution、code_review、checkpoint_final_approval、delivery_integration。

### 5.3 阶段说明

#### 1. requirement_analysis

输入包括用户自然语言需求、Workspace 元信息、Pipeline 配置。输出为 requirement_brief。职责是理解需求目标、提取验收标准、识别约束、标记假设与风险。

#### 2. solution_design

输入包括 requirement_brief、代码库目录摘要、必要文件内容。输出为 design_spec。职责是分析影响范围、给出文件级修改建议、设计 API 或数据结构变化、制定测试建议、列出风险。

#### 3. checkpoint_design_approval

审核对象包括 requirement_brief 和 design_spec。Approve 后进入 code_generation。Reject 时回退到 solution_design，并将 Reject 理由注入下一次设计上下文。

#### 4. code_generation

输入包括已批准的 design_spec、必要代码上下文、Reject 历史。输出为 change_set、diff_manifest、patch_apply_result。职责是 Agent 生成 patch、系统 apply patch、系统生成 diff、系统记录变更文件。约束包括：Agent 不直接修改真实仓库、Agent 不直接写入原始代码库、patch apply 由系统工具执行、patch apply 失败时最多重试 2 次。

#### 5. test_generation_and_execution

输入包括 requirement_brief、design_spec、change_set、diff_manifest。输出为 test_report。内部子步骤包括 test_generation、test_patch_apply、test_execution。职责是生成或更新测试、应用测试 patch、执行测试命令、保存 stdout stderr exit_code duration。

#### 6. code_review

输入包括 design_spec、change_set、diff_manifest、test_report。输出为 review_report。职责是审查正确性、审查安全风险、审查代码规范、审查测试覆盖、给出是否建议交付。

#### 7. checkpoint_final_approval

审核对象包括 change_set、diff_manifest、test_report、review_report。Approve 后进入 delivery_integration。Reject 时默认回退到 code_generation，若 Reject 理由只涉及测试，可回退到 test_generation_and_execution。

#### 8. delivery_integration

输入包括已批准的 change_set、已批准的 review_report、test_report。输出为 delivery_manifest、delivery_summary。职责是生成最终交付清单、生成变更摘要、说明测试结果、说明已知风险、给出后续建议。

---

## 6. 核心领域模型

### 6.1 PipelineTemplate

描述一条可重复运行的流程模板。MVP 内置一条默认模板。关键字段包括 id、name、description、version、template_kind、stages、entry_stage_key、default_provider_id、created_at、updated_at。约束包括：MVP 只支持线性 stages、stages 中每个阶段必须有唯一 key、checkpoint 阶段必须定义 approve_target 与 reject_target、agent 阶段必须绑定 agent_profile_id。

### 6.2 StageDefinition

描述模板中的阶段定义。关键字段包括 key、name、stage_type（agent 或 checkpoint）、depends_on、agent_profile_id、input_artifact_rules、output_artifact_types、provider_policy、approve_target、reject_target、allowed_reject_targets。约束包括：agent 阶段必须绑定 agent_profile_id、checkpoint 阶段必须定义 approve_target、checkpoint 阶段必须定义 reject_target、allowed_reject_targets 用于限制人工 Reject 时可选回退范围。

### 6.3 PipelineRun

描述一次 Pipeline 执行实例。关键字段包括 id、template_id、workspace_ref_id、requirement_text、status、current_stage_key、provider_selection_override、resolved_provider_map、created_at、started_at、ended_at、failure_reason。

状态包括：draft、ready、running、paused、waiting_checkpoint、succeeded、failed、terminated。

状态语义：draft 表示已创建但未完成预检；ready 表示预检通过等待启动；running 表示正在执行；paused 表示人工暂停；waiting_checkpoint 表示等待人工审批；succeeded 表示全部完成；failed 表示执行失败；terminated 表示人工终止。

### 6.4 StageRun

描述某次 Run 中一个阶段的执行记录。关键字段包括 id、run_id、stage_key、agent_profile_id、resolved_provider_id、status、attempt、input_artifact_refs、output_artifact_refs、started_at、ended_at、error_message、raw_response_path。状态包括：pending、running、succeeded、failed、skipped、retrying。

### 6.5 Artifact

描述阶段产物。关键字段包括 id、run_id、stage_run_id、artifact_type、schema_version、content_summary、storage_uri、created_at。存储策略：小 JSON 直接存 SQLite，大文本（如代码、diff）存文件系统，URI 指向文件。

### 6.6 CheckpointRecord

描述人工检查点审批记录。关键字段包括 id、run_id、stage_key、checkpoint_type（design_approval 或 final_approval）、status（pending、approved、rejected）、decision_by、decision_at、reason、next_stage_key。

### 6.7 Workspace

描述隔离工作区。关键字段包括 id、run_id、source_repo_path、workspace_path、git_commit_at_create、status（active、archived、corrupted）、created_at、archived_at。

### 6.8 ProviderConfig

描述 LLM Provider 配置。关键字段包括 id、name、provider_type（openai、anthropic、mock）、api_base、api_key_encrypted、default_model、enabled、priority、created_at、updated_at。

---

## 7. Artifact 类型定义

### 7.1 requirement_brief

```json
{
  "schema_version": "1.0",
  "goal": "string",
  "acceptance_criteria": ["string"],
  "constraints": ["string"],
  "assumptions": ["string"],
  "risks": ["string"],
  "estimated_effort": "small | medium | large"
}
```

### 7.2 design_spec

```json
{
  "schema_version": "1.0",
  "summary": "string",
  "affected_files": [
    {
      "path": "string",
      "change_type": "create | modify | delete",
      "reason": "string"
    }
  ],
  "api_changes": [...],
  "data_changes": [...],
  "test_strategy": "string",
  "risks": [...]
}
```

### 7.3 change_set

```json
{
  "schema_version": "1.0",
  "files": [
    {
      "path": "string",
      "change_type": "create | modify | delete",
      "content": "string (optional)",
      "patch": "string (unified diff format)"
    }
  ],
  "reasoning": "string"
}
```

### 7.4 diff_manifest

```json
{
  "schema_version": "1.0",
  "base_commit": "string",
  "changed_files": ["string"],
  "diff_path": "string",
  "stats": {
    "files_changed": 0,
    "insertions": 0,
    "deletions": 0
  }
}
```

### 7.5 test_report

```json
{
  "schema_version": "1.0",
  "exit_code": 0,
  "stdout": "string",
  "stderr": "string",
  "duration_ms": 0,
  "summary": {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "skipped": 0
  }
}
```

### 7.6 review_report

```json
{
  "schema_version": "1.0",
  "recommendation": "approve | reject | needs_improvement",
  "scores": {
    "correctness": 0,
    "security": 0,
    "style": 0,
    "test_coverage": 0
  },
  "issues": [
    {
      "severity": "critical | major | minor | info",
      "category": "string",
      "description": "string",
      "suggestion": "string"
    }
  ],
  "summary": "string"
}
```

### 7.7 delivery_summary

```json
{
  "schema_version": "1.0",
  "status": "ready | needs_fix",
  "deliverables": ["string"],
  "test_summary": "string",
  "known_risks": ["string"],
  "next_steps": ["string"]
}
```

---

## 8. 状态机设计

### 8.1 PipelineRun 状态机

```
                    +-----------+
         +--------->|   draft   |
         |          +-----+-----+
         |                |
         |                v
         |          +-----------+
         |          |   ready   |
         |          +-----+-----+
         |                |
         |                v
         |          +-----------+     +------------------+
         |          |  running  |<--->| waiting_checkpoint |
         |          +-----+-----+     +--------+---------+
         |                |                    |
         |        +-------+-------+            |
         |        |       |       |            v
         |        v       v       v       +-----------+
         |    +--------+ +------+ +------+|  paused   |
         |    |succeeded| |failed| |terminated|
         |    +--------+ +------+ +------+
         |
         +----------------------------------+
```

状态转换规则：draft → ready（预检通过）；ready → running（用户启动）；running → waiting_checkpoint（遇到 checkpoint 阶段）；waiting_checkpoint → running（用户 Approve）；waiting_checkpoint → running 回退（用户 Reject，携带 reason）；running → paused（用户暂停）；paused → running（用户恢复）；running → succeeded（全部阶段完成）；running → failed（阶段执行失败且重试耗尽）；任意 → terminated（用户终止）。

### 8.2 StageRun 状态机

```
+---------+    +---------+    +----------+
| pending |--->| running |--->| succeeded |
+---------+    +----+----+    +----------+
                    |
                    v
              +----------+    +----------+
              |  failed  |--->| retrying |
              +----------+    +----+-----+
                                     |
                                     v
                              +----------+
                              | succeeded |
                              |  failed   |
                              +----------+
```

---

## 9. Checkpoint 机制

### 9.1 审批流程

Stage 执行到 checkpoint 时，PipelineRun 进入 waiting_checkpoint。系统创建 CheckpointRecord，status=pending。用户通过 API 提交 Approve 或 Reject。Approve 时更新 status=approved，PipelineRun 进入 running，跳转到 approve_target。Reject 时更新 status=rejected，记录 reason，PipelineRun 进入 running，跳转到 reject_target。

### 9.2 Reject 回退策略

每个 checkpoint 必须定义 reject_target（默认回退目标）和 allowed_reject_targets（用户可选回退范围）。Reject 时携带的 reason 必须写入 Artifact，后续阶段可读取。

---

## 10. Artifact Store

### 10.1 存储策略

| 数据类型 | 存储位置 | 说明                                 |
| -------- | -------- | ------------------------------------ |
| 元数据   | SQLite   | PipelineRun, StageRun, Artifact 记录 |
| 小 JSON  | SQLite   | < 10KB 的产物直接存字段              |
| 大文本   | 文件系统 | > 10KB 的产物存文件，URI 引用        |
| 原始响应 | 文件系统 | Agent 原始输出存档                   |

### 10.2 文件系统布局

```
artifacts/
  {run_id}/
    stage_{stage_key}/
      {artifact_id}_{type}.json
      raw_response_{timestamp}.txt
```

---

## 11. Workspace 管理

### 11.1 生命周期

创建阶段：PipelineRun 启动时，从 source_repo_path 克隆到 workspace_path。激活阶段：Agent 在此 workspace 中执行代码变更。归档阶段：PipelineRun 结束后，保留 workspace 用于审计。清理阶段：可配置自动清理策略。

### 11.2 隔离保证

每个 PipelineRun 有独立 workspace。Agent 不直接操作 source_repo_path。Patch apply 由系统工具执行，失败可回滚。Git 操作使用独立 git config。

---

## 12. Provider 注册表

### 12.1 Provider 接口

```python
class LLMProvider(Protocol):
    async def generate(
        self,
        prompt: str,
        schema: dict | None = None
    ) -> dict | str: ...

    async def validate(self) -> bool: ...
```

### 12.2 内置 Provider

内置 Provider 包括：mock（返回固定输出，用于测试）、openai（OpenAI-compatible API）、anthropic（Anthropic Claude API）。

### 12.3 Provider 选择策略

StageDefinition 可指定 provider_policy。PipelineRun 可指定 provider_selection_override。默认使用 PipelineTemplate 的 default_provider_id。

---

## 13. API 设计

### 13.1 Pipeline 管理

```
POST   /api/pipelines              # 创建 PipelineRun
GET    /api/pipelines              # 列表
GET    /api/pipelines/{id}         # 详情
POST   /api/pipelines/{id}/start   # 启动
POST   /api/pipelines/{id}/pause   # 暂停
POST   /api/pipelines/{id}/resume  # 恢复
POST   /api/pipelines/{id}/terminate # 终止
GET    /api/pipelines/{id}/timeline # 阶段时间线
```

### 13.2 Checkpoint

```
POST   /api/checkpoints/{id}/approve  # 审批通过
POST   /api/checkpoints/{id}/reject   # 审批拒绝
```

### 13.3 Artifact

```
GET    /api/artifacts/{id}           # 获取产物
GET    /api/pipelines/{id}/artifacts # 获取 Run 的所有产物
```

### 13.4 Workspace

```
POST   /api/workspaces               # 注册仓库
GET    /api/workspaces               # 列表
GET    /api/workspaces/{id}          # 详情
GET    /api/workspaces/{id}/diff     # 查看 diff
```

### 13.5 Provider

```
GET    /api/providers                # 列表
POST   /api/providers                # 创建
PUT    /api/providers/{id}           # 更新
POST   /api/providers/{id}/validate  # 验证
```

---

## 14. 错误处理

### 14.1 错误分类

| 类别     | 说明                 | 处理策略                             |
| -------- | -------------------- | ------------------------------------ |
| 输入错误 | 参数校验失败         | 立即返回 400，不记录 Run             |
| 预检错误 | 仓库不存在等         | Run 状态保持 draft，返回错误详情     |
| 执行错误 | Agent 执行失败       | StageRun 标记 failed，触发重试或终止 |
| 系统错误 | 数据库、文件系统错误 | 记录日志，返回 500，人工介入         |

### 14.2 重试策略

patch apply 失败时最多重试 2 次。LLM 调用失败时指数退避，最多 3 次。测试执行失败时不重试，记录结果。

---

## 15. 安全设计

### 15.1 代码安全

Agent 不直接修改原始仓库。所有变更在隔离 workspace 中进行。Patch 应用前可人工审查。禁止执行任意系统命令。

### 15.2 数据安全

API Key 加密存储。Workspace 访问权限控制。Artifact 按需清理。

---

## 16. 前端设计

### 16.1 页面规划

| 页面           | 功能                      |
| -------------- | ------------------------- |
| Pipeline 列表  | 查看所有 Run，状态筛选    |
| Pipeline 详情  | 时间线、产物、审批操作    |
| Workspace 管理 | 注册仓库、查看状态        |
| Provider 配置  | 添加、编辑、验证 Provider |

### 16.2 关键交互

Pipeline 时间线可视化展示各阶段状态。Checkpoint 审批展示上下文，支持 Approve/Reject。Diff 查看器用于代码变更对比。Artifact 查看器结构化展示产物。

---

## 17. 测试策略

### 17.1 单元测试

单元测试覆盖状态机转换、Schema 校验、Artifact 序列化/反序列化。

### 17.2 集成测试

集成测试覆盖 API 端到端、Pipeline 完整流程（Mock Agent）、Workspace 创建与清理。

### 17.3 E2E 测试

E2E 测试覆盖完整需求交付流程、Checkpoint 审批回退、多 Provider 切换。

---

## 18. 部署方案

### 18.1 开发环境

```bash
# 后端
uv venv
uv pip install -r requirements.txt
uv run uvicorn app.main:app --reload

# 前端
npm install
npm run dev
```

### 18.2 生产环境

```bash
# Docker
docker-compose up -d

# 或手动
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 19. 演示场景

### 19.1 推荐第一版演示任务

推荐第一版演示任务：为 DevFlow Engine 增加 GET /api/health 接口，返回 service、status、version、time。

验收标准包括：GET /api/health 返回 200；响应 JSON 包含 service；响应 JSON 包含 status=ok；响应 JSON 包含 version；响应 JSON 包含 time；新增或更新测试；测试通过；OpenAPI 文档中可见。

选择该任务的原因：改动小、风险低、能体现 API-First、能体现代码生成、能体现测试生成、能体现 diff 与 review、适合比赛现场演示。

不建议第一版演示的任务包括：前后端联动复杂页面、登录鉴权、数据库迁移、多 Agent 协作、远程 PR 创建。

---

## 20. 实施里程碑

### Milestone 0：项目骨架

目标是 FastAPI 可启动、React 可启动、SQLite 初始化、OpenAPI 可访问。交付物包括 /docs 可打开、/api/health 可用、前端首页可打开。

### Milestone 1：Pipeline 状态机

目标是创建 PipelineRun、启动 PipelineRun、Stage 顺序推进、StageRun 状态保存。交付物包括 Mock 阶段可从 1 推进到 8、timeline API 可展示阶段状态。

### Milestone 2：Checkpoint 闭环

目标是方案审批 checkpoint、最终确认 checkpoint、Approve 继续、Reject 回退。交付物包括 reject reason 被保存、回退阶段能读取 reject reason。

### Milestone 3：Artifact Store

目标是每阶段保存结构化产物、artifact_id 可查询、大文本落盘。交付物包括 requirement_brief 可查、design_spec 可查、review_report 可查、delivery_summary 可查。

### Milestone 4：Mock Agent 端到端

目标是所有 Agent 使用固定输出、完成完整 Pipeline。交付物包括不依赖 LLM、可稳定跑通演示。

### Milestone 5：Provider 接入

目标是 OpenAI-compatible Provider、Anthropic Provider、Provider validate、structured output 校验。交付物包括至少两个 provider 可配置、阶段可切换 provider。

### Milestone 6：Workspace 与 Patch

目标是注册本机 Git 仓库、创建隔离 workspace、生成 patch、apply patch、生成 diff。交付物包括代码变更发生在隔离目录、diff 可查看、patch 可应用。

### Milestone 7：测试执行

目标是执行测试命令、捕获 stdout/stderr、保存 test_report。交付物包括测试失败不阻塞流程、test_report 结构化保存。

### Milestone 8：前端控制台

目标是 Pipeline 列表页、Pipeline 详情页（时间线）、Checkpoint 审批 UI、Diff 查看器。交付物包括可完整演示从需求到交付的流程。

---

## 21. 设计原则回顾

DevFlow Engine 的核心设计目标是：DevFlow Engine 可以稳定编排一个从需求输入到可交付 patch 的 AI 研发流程闭环。

任何时候如果出现"为了过一个场景先硬编码 prompt 或加临时分支"的倾向，都应回到本设计原则：补契约、补状态、补测试、补产物，不要补临时补丁。
