# 2026-04-26 项目目录结构初始化

## 任务概述

根据项目模板创建 DevFlow Engine 的完整目录结构，为后续开发建立基础骨架。

## 执行内容

### 1. Backend 目录结构

创建了 `backend/` 目录，包含以下子模块：

#### API 路由层 (`backend/app/api/`)
- `routes_pipeline.py` - Pipeline 相关接口
- `routes_checkpoint.py` - Checkpoint 检查点接口
- `routes_artifact.py` - Artifact 产物接口
- `routes_workspace.py` - Workspace 工作空间接口
- `routes_provider.py` - LLM Provider 接口

#### 核心逻辑层 (`backend/app/core/`)
- **pipeline/**: 流程编排
  - `orchestrator.py` - 流程编排器
  - `state_machine.py` - 状态机实现
  - `template_loader.py` - 模板加载器

- **execution/**: 执行引擎
  - `executor.py` - 执行器
  - `stage_runner.py` - 阶段运行器

- **checkpoint/**: 检查点管理
  - `checkpoint_service.py` - 检查点服务

- **artifact/**: 产物管理
  - `artifact_service.py` - 产物服务
  - `artifact_store.py` - 产物存储

- **workspace/**: 工作空间管理
  - `workspace_manager.py` - 工作空间管理器
  - `patch_applier.py` - Patch 应用器
  - `command_runner.py` - 命令执行器

- **provider/**: LLM Provider 适配
  - `provider_registry.py` - Provider 注册表
  - `base.py` - 基础接口
  - `openai_compatible.py` - OpenAI 兼容适配器
  - `anthropic.py` - Anthropic 适配器

#### Agent 层 (`backend/app/agents/`)
- `profiles.py` - Agent 配置文件
- `runner.py` - Agent 运行器
- `mock_agents.py` - Mock Agent 实现
- `requirement_agent.py` - 需求分析 Agent
- `design_agent.py` - 方案设计 Agent
- `code_patch_agent.py` - 代码生成 Agent
- `test_agent.py` - 测试 Agent
- `review_agent.py` - 评审 Agent
- `delivery_agent.py` - 交付 Agent

#### 数据模型层 (`backend/app/models/`)
- `pipeline.py` - Pipeline 模型
- `stage.py` - Stage 模型
- `artifact.py` - Artifact 模型
- `checkpoint.py` - Checkpoint 模型
- `workspace.py` - Workspace 模型
- `provider.py` - Provider 模型

#### Schema 定义层 (`backend/app/schemas/`)
- `pipeline.py` - Pipeline Schema
- `artifacts.py` - Artifacts Schema
- `checkpoint.py` - Checkpoint Schema
- `agent_outputs.py` - Agent 输出 Schema
- `workspace.py` - Workspace Schema
- `provider.py` - Provider Schema

#### 数据库层 (`backend/app/db/`)
- `base.py` - 数据库基础
- `session.py` - 会话管理
- `migrations/` - 数据库迁移目录

#### 共享工具层 (`backend/app/shared/`)
- `config.py` - 配置管理
- `errors.py` - 错误定义
- `logging.py` - 日志工具
- `ids.py` - ID 生成器

#### 测试目录 (`backend/tests/`)
- 预留测试文件位置

### 2. Frontend 目录结构

创建了 `frontend/src/` 目录结构：

#### 页面层 (`frontend/src/pages/`)
- `RequirementEntry.tsx` - 需求录入页面
- `DevWorkspace.tsx` - 开发工作空间页面

#### 组件层 (`frontend/src/components/`)
- `RequirementInput.tsx` - 需求输入组件
- `RunTimeline.tsx` - 运行时间线组件
- `ArtifactViewer.tsx` - 产物查看器组件
- `CheckpointPanel.tsx` - 检查点面板组件
- `RunMetricsCard.tsx` - 运行指标卡片组件

#### API 层 (`frontend/src/api/`)
- 预留 API 客户端文件位置

#### 状态管理层 (`frontend/src/store/`)
- 预留状态管理文件位置

## 设计决策

1. **遵循 MVP 优先原则**: 目录结构仅包含 must-have 功能所需模块，当前不做浏览器注入、实时热更新、分布式 Worker 等高级功能

2. **契约优先**: 每个 Agent 和核心模块都有明确的输入/输出 Schema 定义位置

3. **Provider 抽象**: 支持至少 2 个 LLM Provider（OpenAI-compatible 和 Anthropic）

4. **人工检查点**: Checkpoint 相关模块已预留，支持 Approve/Reject/回退机制

5. **安全执行**: Workspace 隔离相关模块已建立，Agent 不直接修改真实仓库

## 下一步计划

1. 实现 `backend/app/core/pipeline/state_machine.py` - 核心状态机
2. 实现 `backend/app/models/` 中的 SQLAlchemy 模型
3. 实现 `backend/app/schemas/` 中的 Pydantic Schema
4. 创建 FastAPI 应用入口和路由注册
5. 实现 Mock Agent 以跑通完整流程

## 相关文件

- 目录结构模板: 用户提供的项目模板
- 设计文档: `journey/design.md`
- 功能边界: `docs/function.md`
