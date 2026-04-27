# Pipeline 产物沉淀与交付闭环 Spec

## Why

Pipeline 流程（需求→方案→编码→测试→评审→交付）可以成功执行所有阶段，但流程完成后未能实现产物沉淀：代码变更未被提交到本地 Git 仓库，也未创建远程仓库或 PR。当前 `delivery_integration` 阶段仅生成一个 `delivery_summary` 文本产物，缺少将代码变更从隔离 workspace 持久化到可交付状态的完整机制。这导致 Pipeline 的核心价值——从需求到可交付代码——在最后一步断裂。

## 业界最佳实践参考

| 项目 | 核心启示 |
|------|---------|
| **Claude Code** (anthropics/claude-code) | 内置专用 git 工具（`git_commit`、`git_branch`），LLM 自动生成 commit message，支持 headless 模式 CI/CD 集成；工具白名单 + 确认机制保障安全 |
| **OpenCode** (sst/opencode) | Git 操作统一封装为 `GitService`；Git 身份隔离（`GIT_AUTHOR_NAME` 等环境变量）；Patch 应用渐进策略（`--check` → 正常 → `--3way` → `--reject`） |
| **Codex CLI** (openai/codex) | `--git-commit` 标志在任务完成后自动 commit；网络隔离沙箱保障安全；`shutil.which("git")` 发现 Git 可执行文件 |
| **Gemini CLI** (google-gemini/gemini-cli) | OS 级沙箱隔离；扩展系统支持自定义持久化逻辑；用户确认机制 |

**关键发现**：所有项目都采用"就地修改 + Git 追踪"范式，Git commit/branch/PR 是代码变更持久化的核心手段。DevFlow Engine 的"隔离 workspace + 结构化 artifact"设计在安全性和可追溯性上优于现有方案，但缺少从 workspace 到可交付 Git 产物的"最后一公里"。

## 问题表现与具体场景

### 场景 1：Pipeline 完成后代码变更丢失

- **WHEN** 用户通过前端完成完整 Pipeline 流程（需求→方案→编码→测试→评审→交付）
- **THEN** PipelineRun 状态为 `succeeded`
- **BUT** 隔离 workspace 中的代码变更未被 commit 到 Git
- **AND** workspace 中的变更仅存在于工作树（working tree），无 Git 历史记录
- **AND** 如果 workspace 被清理，所有代码变更将永久丢失

### 场景 2：无法获取可交付的代码产物

- **WHEN** 用户查看 delivery_integration 阶段的 artifacts
- **THEN** 仅有 `delivery_summary`（文本摘要）
- **BUT** 没有 `delivery_manifest`（交付清单）
- **AND** 没有 `diff_manifest`（变更差异清单）
- **AND** 无法获取可 apply 的 patch 文件
- **AND** 无法获取可 checkout 的 Git 分支

### 场景 3：无法将变更推送到远程仓库

- **WHEN** 用户希望将 Pipeline 产出的代码变更推送到 GitHub/GitLab
- **THEN** 系统无任何远程仓库集成能力
- **AND** 无法自动创建远程仓库
- **AND** 无法自动创建 PR/MR
- **AND** 无法通过飞书通知交付结果

## 根因分析

### RC1: `delivery_integration` 阶段职责不完整（CRITICAL）

- **位置**: `stage_runner.py:153-159`, `delivery_agent.py`
- **症状**: Pipeline 最后阶段仅生成 `delivery_summary` 文本产物，不执行任何 Git 操作
- **根因**: `delivery_agent` 的 profile 仅要求 LLM 生成交付摘要，不包含 Git commit/branch/push 等操作。`stage_runner.py` 中 `delivery_integration` 的输入组装仅传递 `change_set`、`review_report`、`test_report`，不传递 workspace 信息
- **影响**: Pipeline 的核心产出（代码变更）停留在"已 apply 但未 commit"状态，无法作为可交付物

**代码证据**:
```python
# stage_runner.py:153-159 — delivery_integration 输入组装
elif stage_key == "delivery_integration":
    if "change_set" in artifact_map:
        input_data["change_set"] = artifact_map["change_set"]
    if "review_report" in artifact_map:
        input_data["review_report"] = artifact_map["review_report"]
    if "test_report" in artifact_map:
        input_data["test_report"] = artifact_map["test_report"]
    # 缺少：workspace 信息、diff_manifest、Git 操作指令
```

### RC2: 代码变更 apply 后无最终 Git Commit（CRITICAL）

- **位置**: `stage_runner.py:245-264`, `workspace_manager.py:333-351`
- **症状**: `code_generation` 阶段 apply patch 后，workspace 中存在未提交的变更
- **根因**: `_snapshot_before_stage` 在每个阶段前创建临时 commit（"snapshot: before {stage_key}"），但 `delivery_integration` 完成后没有创建最终的交付 commit。`snapshot_workspace` 的 commit message 是临时性的，不适合作为交付记录
- **影响**: workspace 中的代码变更无法通过 `git log` 追溯，无法通过 `git checkout` 恢复

**代码证据**:
```python
# workspace_manager.py:339-341 — snapshot commit 使用临时 message
run_git(["add", "-A"], cwd=str(ws_path), timeout=30)
result = run_git(
    ["commit", "-m", f"snapshot: {message}", "--allow-empty"],
    cwd=str(ws_path), timeout=30,
)
# 缺少：交付完成后的正式 commit（如 "feat: implement {requirement_goal}"）
```

### RC3: `diff_manifest` Artifact 定义但从未生成（HIGH）

- **位置**: `artifacts.py:DiffManifest` schema, `stage_runner.py`
- **症状**: `diff_manifest` 在 schema 中定义，但 Pipeline 流程中从未生成和保存该 artifact
- **根因**: `code_generation` 阶段完成后，`stage_runner.py` 不调用 `generate_diff()` 生成 `diff_manifest`。`patch_applier.py` 中有 `generate_diff()` 函数，但未在 Pipeline 流程中被调用
- **影响**: 下游阶段（code_review、delivery_integration）缺少结构化的变更差异信息，无法准确评估变更范围

### RC4: 无 Feature Branch 创建机制（HIGH）

- **位置**: `workspace_manager.py`, `stage_runner.py`
- **症状**: Pipeline 在 workspace 的默认分支上直接操作，不创建 feature branch
- **根因**: 设计文档将"Git 分支 commit PR/MR 集成"列为"保留扩展位"，MVP 未实现。但缺少 feature branch 导致：1) 无法隔离交付变更；2) 无法创建 PR；3) 变更与原始代码混在一起
- **影响**: 无法通过 Git 分支模型管理交付物，无法创建 PR/MR

### RC5: 无远程仓库集成能力（MEDIUM）

- **位置**: 无相关代码
- **症状**: 系统无法推送到 GitHub/GitLab，无法创建远程仓库，无法创建 PR
- **根因**: 设计文档将"远程仓库自动操作"列为"当前不做"。但完全缺乏远程集成能力导致 Pipeline 产出无法到达最终交付目标
- **影响**: 用户需手动将 workspace 中的变更复制到远程仓库，违背自动化交付的目标

### RC6: `delivery_manifest` Artifact 未实现（MEDIUM）

- **位置**: 设计文档 §8 delivery_integration 描述
- **症状**: 设计文档要求 `delivery_integration` 输出 `delivery_manifest` 和 `delivery_summary`，但当前仅实现 `delivery_summary`
- **根因**: `delivery_agent` profile 的 `output_schema` 映射到 `delivery_summary`，未包含 `delivery_manifest`
- **影响**: 缺少结构化的交付清单，无法明确列出交付物（文件列表、commit hash、branch name 等）

### RC7: Workspace 生命周期缺少"交付归档"阶段（MEDIUM）

- **位置**: `workspace_manager.py`, `orchestrator.py`
- **症状**: Pipeline 完成后 workspace 保持 `active` 状态，无归档逻辑
- **根因**: `archive_workspace` 函数存在但未在 Pipeline 完成时自动调用。`handle_stage_success` 中当 PipelineRun 状态变为 `succeeded` 时不触发 workspace 归档
- **影响**: Workspace 可能被后续操作覆盖，交付产物缺乏持久化保障

## What Changes

- 新增 `backend/app/core/workspace/delivery_service.py`：交付服务，封装 Git commit/branch/push 操作
- 修改 `stage_runner.py`：在 `delivery_integration` 阶段执行交付 Git 操作（commit + branch + diff 生成）
- 修改 `stage_runner.py`：在 `code_generation` 阶段完成后生成 `diff_manifest` artifact
- 修改 `artifacts.py`：新增 `DeliveryManifest` schema
- 修改 `ARTIFACT_TYPE_TO_SCHEMA` 和 `OUTPUT_SCHEMA_TO_ARTIFACT_TYPE` 映射表
- 修改 `orchestrator.py`：PipelineRun 完成时归档 workspace
- 修改 `delivery_agent` profile：增加交付上下文信息
- 新增 `backend/app/api/routes_delivery.py`：交付相关 API（获取 patch、推送远程等）
- 新增远程仓库集成能力（GitHub API + 飞书通知）

## Impact

- Affected specs: Pipeline 执行流程, Artifact 类型定义, Workspace 生命周期, Agent Profile
- Affected code:
  - `backend/app/core/workspace/delivery_service.py` — **新增**：交付 Git 操作封装
  - `backend/app/core/execution/stage_runner.py` — 交付阶段增强、diff_manifest 生成
  - `backend/app/schemas/artifacts.py` — 新增 DeliveryManifest schema
  - `backend/app/agents/profiles.py` — delivery_agent profile 增强
  - `backend/app/core/pipeline/orchestrator.py` — 完成时归档 workspace
  - `backend/app/core/workspace/workspace_manager.py` — 交付 commit 支持
  - `backend/app/api/routes_delivery.py` — **新增**：交付 API
  - `backend/app/main.py` — 注册新路由

## ADDED Requirements

### Requirement: 交付 Git Commit

Pipeline 完成后 SHALL 在 workspace 中创建正式的交付 Git commit，包含所有代码变更。

#### Scenario: Pipeline 成功完成后创建交付 commit
- **WHEN** PipelineRun 状态变为 `succeeded`
- **THEN** 在 workspace 中执行 `git add -A` + `git commit`
- **AND** commit message 包含需求目标摘要（从 `requirement_brief.goal` 提取）
- **AND** commit message 格式为 `feat: {goal_summary}`
- **AND** commit 使用 DevFlow 身份（`GIT_AUTHOR_NAME=devflow`）
- **AND** 生成的 commit hash 记录到 `delivery_manifest` artifact

#### Scenario: Workspace 中无代码变更
- **WHEN** PipelineRun 完成但 workspace 中无未提交变更
- **THEN** 跳过交付 commit
- **AND** `delivery_manifest` 中标记 `has_changes=false`

### Requirement: Feature Branch 创建

Pipeline 交付时 SHALL 在 workspace 中创建 feature branch，隔离交付变更。

#### Scenario: 创建 feature branch
- **WHEN** 交付 commit 创建成功
- **THEN** 从当前 HEAD 创建 feature branch，命名格式为 `devflow/{run_id[:12]}`
- **AND** 切换到 feature branch
- **AND** 交付 commit 位于 feature branch 上
- **AND** branch name 记录到 `delivery_manifest` artifact

#### Scenario: Feature branch 已存在
- **WHEN** 同名 feature branch 已存在
- **THEN** 删除旧 branch 后重新创建
- **AND** 记录 warning 日志

### Requirement: diff_manifest Artifact 生成

`code_generation` 阶段完成后 SHALL 生成 `diff_manifest` artifact。

#### Scenario: 代码变更后生成 diff_manifest
- **WHEN** `code_generation` 阶段成功完成且 workspace 中有代码变更
- **THEN** 调用 `generate_diff(workspace_path)` 获取变更信息
- **AND** 将结果保存为 `diff_manifest` artifact
- **AND** `diff_manifest` 包含 `base_commit`、`changed_files`、`stats`

#### Scenario: 无 workspace 可用
- **WHEN** `code_generation` 阶段完成但无 workspace
- **THEN** 跳过 `diff_manifest` 生成
- **AND** 记录 warning 日志

### Requirement: delivery_manifest Artifact

系统 SHALL 在 `delivery_integration` 阶段生成 `delivery_manifest` artifact，结构化记录所有交付物。

#### Scenario: 生成 delivery_manifest
- **WHEN** `delivery_integration` 阶段执行
- **THEN** 生成 `delivery_manifest`，包含以下字段：
  - `commit_hash`: 交付 commit 的 hash
  - `branch_name`: feature branch 名称
  - `changed_files`: 变更文件列表
  - `diff_stats`: 变更统计（insertions/deletions/files_changed）
  - `has_changes`: 是否有代码变更
  - `artifacts`: 关联 artifact ID 列表
  - `delivery_summary_ref`: delivery_summary artifact ID
- **AND** `delivery_manifest` 作为独立 artifact 保存

### Requirement: 交付服务封装

参考 Claude Code 的内置 git 工具和 OpenCode 的 `GitService` 模式，新增 `DeliveryService` 封装交付 Git 操作。

#### Scenario: 执行交付 Git 操作
- **WHEN** `delivery_integration` 阶段需要执行 Git 操作
- **THEN** 通过 `DeliveryService` 统一调用：
  - `commit_delivery_changes(workspace_path, goal_summary)` — 创建交付 commit
  - `create_delivery_branch(workspace_path, run_id)` — 创建 feature branch
  - `generate_delivery_diff(workspace_path)` — 生成交付 diff
- **AND** 所有 Git 操作通过 `run_git()` 执行
- **AND** 所有 Git 操作使用 DevFlow 身份隔离

#### Scenario: Git 操作失败
- **WHEN** 交付 commit 或 branch 创建失败
- **THEN** 记录 error 日志
- **AND** `delivery_manifest` 中标记 `has_changes=false` 和错误信息
- **AND** 不阻塞 Pipeline 完成（交付 Git 操作为 best-effort）

### Requirement: Pipeline 完成时 Workspace 归档

PipelineRun 完成后 SHALL 自动归档 workspace。

#### Scenario: Pipeline 成功完成后归档
- **WHEN** PipelineRun 状态变为 `succeeded`
- **THEN** 自动调用 `archive_workspace` 将 workspace 状态设为 `archived`
- **AND** workspace 目录保留用于审计

#### Scenario: Pipeline 失败后归档
- **WHEN** PipelineRun 状态变为 `failed`
- **THEN** 同样归档 workspace
- **AND** workspace 中的变更保留用于诊断

### Requirement: 交付 API

新增交付相关 API 端点，支持获取交付产物和推送到远程仓库。

#### Scenario: 获取交付 patch
- **WHEN** 用户调用 `GET /api/pipelines/{id}/delivery/patch`
- **THEN** 返回 workspace 中 feature branch 相对于 base commit 的 unified diff
- **AND** 响应 Content-Type 为 `text/x-diff`

#### Scenario: 获取交付信息
- **WHEN** 用户调用 `GET /api/pipelines/{id}/delivery`
- **THEN** 返回 `delivery_manifest` 和 `delivery_summary` 的合并信息
- **AND** 包含 commit hash、branch name、changed files、diff stats

#### Scenario: 推送到远程仓库
- **WHEN** 用户调用 `POST /api/pipelines/{id}/delivery/push`
- **AND** 请求体包含 `remote_url` 和可选的 `remote_branch`
- **THEN** 将 feature branch push 到指定的远程仓库
- **AND** 返回 push 结果（成功/失败、远程 URL）

#### Scenario: 创建 GitHub PR
- **WHEN** 用户调用 `POST /api/pipelines/{id}/delivery/pr`
- **AND** 请求体包含 `repo_owner`、`repo_name`、`base_branch`
- **THEN** 通过 GitHub API 创建 Pull Request
- **AND** PR 标题为需求目标摘要
- **AND** PR 描述包含 design_spec 摘要、test_report 摘要、review_report 摘要
- **AND** 返回 PR URL

### Requirement: 飞书交付通知

Pipeline 交付完成后 SHALL 通过飞书 Webhook 发送交付通知。

#### Scenario: 交付成功通知
- **WHEN** PipelineRun 状态变为 `succeeded` 且交付 commit 创建成功
- **THEN** 通过配置的飞书 Webhook URL 发送通知
- **AND** 通知内容包括：需求目标、commit hash、branch name、变更文件数、测试结果摘要
- **AND** 通知格式为飞书卡片消息

#### Scenario: 飞书 Webhook 未配置
- **WHEN** 环境变量 `FEISHU_WEBHOOK_URL` 未设置
- **THEN** 跳过飞书通知
- **AND** 记录 info 日志

## MODIFIED Requirements

### Requirement: delivery_integration 阶段职责

原要求中 `delivery_integration` 仅生成 `delivery_summary`，现修改为：

1. 执行交付 Git 操作（commit + branch），通过 `DeliveryService` 封装
2. 生成 `delivery_manifest` artifact，结构化记录交付物
3. 生成 `delivery_summary` artifact（保留原有功能）
4. 交付 Git 操作为 best-effort，失败不阻塞 Pipeline 完成

### Requirement: code_generation 阶段输出

原要求中 `code_generation` 阶段输出 `change_set` 和 `diff_manifest`，但实际仅输出 `change_set`。现修改为：

1. 输出 `change_set`（保留原有功能）
2. 额外生成 `diff_manifest` artifact，通过 `generate_diff()` 获取

### Requirement: Workspace 生命周期

原要求中 Workspace 生命周期为"创建→激活→归档→清理"，但归档从未自动触发。现修改为：

1. PipelineRun 状态变为 `succeeded` 或 `failed` 时，自动归档 workspace
2. 归档前确保交付 commit 已创建

## REMOVED Requirements

无。
