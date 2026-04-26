# Tasks

## Milestone 0: 项目骨架

- [ ] Task 1: 创建后端 Python 项目基础设施
  - [ ] SubTask 1.1: 创建 `pyproject.toml`，声明依赖（fastapi、uvicorn、sqlalchemy、aiosqlite、pydantic、httpx、python-dotenv、cryptography）
  - [ ] SubTask 1.2: 创建所有 `__init__.py` 包文件（app、api、core、core/pipeline、core/execution、core/checkpoint、core/artifact、core/workspace、core/provider、db、models、schemas、agents、shared）
  - [ ] SubTask 1.3: 实现 `backend/app/shared/config.py`（Settings 类，读取环境变量，配置数据库路径、artifact 存储路径、workspace 根路径）
  - [ ] SubTask 1.4: 实现 `backend/app/shared/ids.py`（生成 UUID 格式的唯一 ID）
  - [ ] SubTask 1.5: 实现 `backend/app/shared/errors.py`（自定义异常类：InputError、PrecheckError、ExecutionError、SystemError）
  - [ ] SubTask 1.6: 实现 `backend/app/shared/logging.py`（配置结构化日志）
  - [ ] SubTask 1.7: 实现 `backend/app/main.py`（FastAPI app 创建、lifespan 事件、路由注册、`/api/health` 端点）

- [ ] Task 2: 创建前端 React 项目基础设施
  - [ ] SubTask 2.1: 初始化 Vite + React + TypeScript 项目（package.json、vite.config.ts、tsconfig.json、index.html）
  - [ ] SubTask 2.2: 安装前端依赖（react-router-dom、antd、@ant-design/icons、axios）
  - [ ] SubTask 2.3: 创建 `src/App.tsx` 路由配置和 `src/main.tsx` 入口

## Milestone 1: 数据库层与领域模型

- [ ] Task 3: 实现 SQLite 数据库层
  - [ ] SubTask 3.1: 实现 `backend/app/db/session.py`（async session 工厂、get_db 依赖注入）
  - [ ] SubTask 3.2: 实现 `backend/app/db/base.py`（SQLAlchemy Base、init_db 函数自动建表）

- [ ] Task 4: 实现领域模型（SQLAlchemy ORM Models）
  - [ ] SubTask 4.1: 实现 `backend/app/models/pipeline.py`（PipelineTemplate、PipelineRun 模型，含所有字段和状态枚举）
  - [ ] SubTask 4.2: 实现 `backend/app/models/stage.py`（StageDefinition、StageRun 模型，含状态枚举）
  - [ ] SubTask 4.3: 实现 `backend/app/models/artifact.py`（Artifact 模型，含 storage_uri、content 字段）
  - [ ] SubTask 4.4: 实现 `backend/app/models/checkpoint.py`（CheckpointRecord 模型，含 status 枚举）
  - [ ] SubTask 4.5: 实现 `backend/app/models/workspace.py`（Workspace 模型，含 status 枚举）
  - [ ] SubTask 4.6: 实现 `backend/app/models/provider.py`（ProviderConfig 模型，含 api_key_encrypted）

## Milestone 2: Schema 定义与校验

- [ ] Task 5: 实现 Pydantic Schema 定义
  - [ ] SubTask 5.1: 实现 `backend/app/schemas/pipeline.py`（PipelineRunCreate、PipelineRunResponse、PipelineRunListResponse、StageRunResponse、TimelineResponse）
  - [ ] SubTask 5.2: 实现 `backend/app/schemas/artifacts.py`（RequirementBrief、DesignSpec、ChangeSet、DiffManifest、TestReport、ReviewReport、DeliverySummary 的 Pydantic 模型，含 Schema 校验）
  - [ ] SubTask 5.3: 实现 `backend/app/schemas/checkpoint.py`（CheckpointApproveRequest、CheckpointRejectRequest、CheckpointResponse）
  - [ ] SubTask 5.4: 实现 `backend/app/schemas/provider.py`（ProviderCreate、ProviderUpdate、ProviderResponse）
  - [ ] SubTask 5.5: 实现 `backend/app/schemas/workspace.py`（WorkspaceRegister、WorkspaceResponse、DiffResponse）
  - [ ] SubTask 5.6: 实现 `backend/app/schemas/agent_outputs.py`（各 Agent 的输入/输出 Schema）

## Milestone 3: Pipeline 状态机与编排

- [ ] Task 6: 实现 Pipeline 状态机
  - [ ] SubTask 6.1: 实现 `backend/app/core/pipeline/state_machine.py`（PipelineRunStateMachine：定义合法状态转换、转换方法、转换校验）
  - [ ] SubTask 6.2: 实现 StageRunStateMachine（定义合法状态转换、转换方法、转换校验）

- [ ] Task 7: 实现 Pipeline Template Loader
  - [ ] SubTask 7.1: 实现 `backend/app/core/pipeline/template_loader.py`（加载 feature_delivery_default 模板，定义 8 个 StageDefinition，包含 stage_type、depends_on、agent_profile_id、approve_target、reject_target）

- [ ] Task 8: 实现 Pipeline Orchestrator
  - [ ] SubTask 8.1: 实现 `backend/app/core/pipeline/orchestrator.py`（创建 PipelineRun、启动 PipelineRun、推进阶段、暂停/恢复/终止、处理 checkpoint 暂停和恢复）

## Milestone 4: 核心服务实现

- [ ] Task 9: 实现 Artifact Store
  - [ ] SubTask 9.1: 实现 `backend/app/core/artifact/artifact_store.py`（文件系统存储：save_artifact_file、load_artifact_file、创建目录结构）
  - [ ] SubTask 9.2: 实现 `backend/app/core/artifact/artifact_service.py`（save_artifact：判断大小选择存储策略、load_artifact：自动从文件系统读取、list_artifacts_by_run）

- [ ] Task 10: 实现 Checkpoint Service
  - [ ] SubTask 10.1: 实现 `backend/app/core/checkpoint/checkpoint_service.py`（create_checkpoint、approve_checkpoint、reject_checkpoint、get_pending_checkpoint）

- [ ] Task 11: 实现 Workspace Manager
  - [ ] SubTask 11.1: 实现 `backend/app/core/workspace/workspace_manager.py`（register_repo：验证路径和 Git 仓库、create_workspace：克隆到隔离目录、archive_workspace、get_diff）
  - [ ] SubTask 11.2: 实现 `backend/app/core/workspace/patch_applier.py`（apply_patch：在 workspace 中应用 unified diff、generate_diff：生成 diff_manifest）
  - [ ] SubTask 11.3: 实现 `backend/app/core/workspace/command_runner.py`（run_command：执行测试命令、捕获 stdout/stderr/exit_code/duration_ms）

## Milestone 5: Provider 与 Agent 实现

- [ ] Task 12: 实现 Provider Registry
  - [ ] SubTask 12.1: 实现 `backend/app/core/provider/base.py`（LLMProvider Protocol：generate、validate 方法）
  - [ ] SubTask 12.2: 实现 `backend/app/core/provider/provider_registry.py`（注册/获取 Provider、resolve_provider 根据 policy 和 override 选择 Provider）
  - [ ] SubTask 12.3: 实现 `backend/app/core/provider/openai_compatible.py`（OpenAI-compatible API 适配器，支持 structured output）
  - [ ] SubTask 12.4: 实现 `backend/app/core/provider/anthropic.py`（Anthropic Claude API 适配器，支持 structured output）

- [ ] Task 13: 实现 Agent 框架
  - [ ] SubTask 13.1: 实现 `backend/app/agents/profiles.py`（AgentProfile 定义：role、system_prompt、input_schema、output_schema、tools）
  - [ ] SubTask 13.2: 实现 `backend/app/agents/runner.py`（AgentRunner：加载 profile、组装 prompt、调用 Provider、校验输出 Schema）

- [ ] Task 14: 实现 Mock Agent
  - [ ] SubTask 14.1: 实现 `backend/app/agents/mock_agents.py`（6 个 Mock Agent：返回符合 Schema 的固定输出，用于完整闭环测试）

- [ ] Task 15: 实现真实 Agent
  - [ ] SubTask 15.1: 实现 `backend/app/agents/requirement_agent.py`（输入需求文本，输出 requirement_brief）
  - [ ] SubTask 15.2: 实现 `backend/app/agents/design_agent.py`（输入 requirement_brief + 代码库上下文，输出 design_spec）
  - [ ] SubTask 15.3: 实现 `backend/app/agents/code_patch_agent.py`（输入 design_spec + 代码上下文，输出 change_set）
  - [ ] SubTask 15.4: 实现 `backend/app/agents/test_agent.py`（输入 change_set + requirement_brief，生成测试、执行测试，输出 test_report）
  - [ ] SubTask 15.5: 实现 `backend/app/agents/review_agent.py`（输入 design_spec + change_set + test_report，输出 review_report）
  - [ ] SubTask 15.6: 实现 `backend/app/agents/delivery_agent.py`（输入已批准 change_set + review_report + test_report，输出 delivery_summary）

## Milestone 6: Executor 与 Stage Runner

- [ ] Task 16: 实现 Executor
  - [ ] SubTask 16.1: 实现 `backend/app/core/execution/stage_runner.py`（执行单个阶段：加载 Agent、组装输入、调用 Agent、保存 Artifact、更新 StageRun 状态）
  - [ ] SubTask 16.2: 实现 `backend/app/core/execution/executor.py`（协调阶段执行：从 Orchestrator 接收阶段执行请求、调用 StageRunner、处理重试逻辑、通知 Orchestrator 结果）

## Milestone 7: REST API 实现

- [ ] Task 17: 实现 API 路由
  - [ ] SubTask 17.1: 实现 `backend/app/api/routes_pipeline.py`（POST /api/pipelines、GET /api/pipelines、GET /api/pipelines/{id}、POST /api/pipelines/{id}/start、POST /api/pipelines/{id}/pause、POST /api/pipelines/{id}/resume、POST /api/pipelines/{id}/terminate、GET /api/pipelines/{id}/timeline）
  - [ ] SubTask 17.2: 实现 `backend/app/api/routes_checkpoint.py`（POST /api/checkpoints/{id}/approve、POST /api/checkpoints/{id}/reject）
  - [ ] SubTask 17.3: 实现 `backend/app/api/routes_artifact.py`（GET /api/artifacts/{id}、GET /api/pipelines/{id}/artifacts）
  - [ ] SubTask 17.4: 实现 `backend/app/api/routes_workspace.py`（POST /api/workspaces、GET /api/workspaces、GET /api/workspaces/{id}、GET /api/workspaces/{id}/diff）
  - [ ] SubTask 17.5: 实现 `backend/app/api/routes_provider.py`（GET /api/providers、POST /api/providers、PUT /api/providers/{id}、POST /api/providers/{id}/validate）

## Milestone 8: 前端控制台

- [ ] Task 18: 实现前端 API 层与状态管理
  - [ ] SubTask 18.1: 实现 `frontend/src/api/client.ts`（axios 实例、API 调用函数）
  - [ ] SubTask 18.2: 实现 `frontend/src/store/`（Pipeline 状态管理、使用 React Context 或 zustand）

- [ ] Task 19: 实现前端页面与组件
  - [ ] SubTask 19.1: 实现 `frontend/src/pages/RequirementEntry.tsx`（需求输入页面：文本输入框、创建 PipelineRun 按钮）
  - [ ] SubTask 19.2: 实现 `frontend/src/pages/DevWorkspace.tsx`（Pipeline 详情页：时间线、产物列表、操作按钮）
  - [ ] SubTask 19.3: 实现 `frontend/src/components/RunTimeline.tsx`（阶段时间线组件：展示 8 个阶段状态和耗时）
  - [ ] SubTask 19.4: 实现 `frontend/src/components/CheckpointPanel.tsx`（审批面板：展示上下文、Approve/Reject 按钮、Reject reason 输入）
  - [ ] SubTask 19.5: 实现 `frontend/src/components/ArtifactViewer.tsx`（产物查看器：结构化展示各类 Artifact）
  - [ ] SubTask 19.6: 实现 `frontend/src/components/RunMetricsCard.tsx`（运行指标卡片：状态、耗时、阶段进度）
  - [ ] SubTask 19.7: 实现 `frontend/src/components/RequirementInput.tsx`（需求输入组件：文本框 + 提交）

## Milestone 9: 端到端集成与测试

- [ ] Task 20: 实现端到端集成
  - [ ] SubTask 20.1: 确保 Mock Agent 完整闭环可运行（从需求输入到 delivery_summary 输出）
  - [ ] SubTask 20.2: 确保两个 Checkpoint 的 Approve/Reject 流程正确
  - [ ] SubTask 20.3: 确保 Reject 回退后 Agent 可读取 Reject reason
  - [ ] SubTask 20.4: 确保自举演示可运行（为自身添加 health 接口）

- [ ] Task 21: 编写测试
  - [ ] SubTask 21.1: 单元测试：状态机转换、Schema 校验、Artifact 序列化
  - [ ] SubTask 21.2: 集成测试：API 端到端、Pipeline 完整流程（Mock Agent）、Workspace 创建
  - [ ] SubTask 21.3: E2E 测试：完整需求交付流程、Checkpoint 审批回退

# Task Dependencies

- Task 2 可与 Task 1 并行
- Task 3 依赖 Task 1
- Task 4 依赖 Task 3
- Task 5 依赖 Task 1
- Task 6 依赖 Task 4、Task 5
- Task 7 依赖 Task 5
- Task 8 依赖 Task 6、Task 7
- Task 9 依赖 Task 3、Task 4、Task 5
- Task 10 依赖 Task 4、Task 5
- Task 11 依赖 Task 3、Task 4
- Task 12 依赖 Task 4、Task 5
- Task 13 依赖 Task 5、Task 12
- Task 14 依赖 Task 13
- Task 15 依赖 Task 13
- Task 16 依赖 Task 8、Task 9、Task 13
- Task 17 依赖 Task 8、Task 9、Task 10、Task 11、Task 12
- Task 18 依赖 Task 2、Task 17
- Task 19 依赖 Task 18
- Task 20 依赖 Task 16、Task 17、Task 19
- Task 21 依赖 Task 20
