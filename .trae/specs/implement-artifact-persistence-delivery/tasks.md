# Tasks

- [x] Task 1: 新增 `DeliveryManifest` Schema 和映射表更新（RC6 基础设施）
  - [x] SubTask 1.1: 在 `artifacts.py` 中新增 `DeliveryManifest` Pydantic model，字段包含 `commit_hash`、`branch_name`、`changed_files`、`diff_stats`、`has_changes`、`artifacts`、`delivery_summary_ref`
  - [x] SubTask 1.2: 在 `ARTIFACT_TYPE_TO_SCHEMA` 映射表中注册 `delivery_manifest` → `DeliveryManifest`
  - [x] SubTask 1.3: 在 `OUTPUT_SCHEMA_TO_ARTIFACT_TYPE` 映射表中添加 `deliverymanifest` → `delivery_manifest` 条目
  - [x] SubTask 1.4: 更新 `delivery_agent` profile 的 `output_schema` 为 `DeliveryAgentOutput`（包含 delivery_summary + delivery_manifest）— delivery_manifest 为程序化生成，无需修改 agent profile

- [x] Task 2: 新增 `DeliveryService` 交付 Git 操作封装（RC1/RC2/RC4 核心修复）
  - [x] SubTask 2.1: 新建 `backend/app/core/workspace/delivery_service.py`，实现 `commit_delivery_changes(workspace_path, goal_summary) -> CommitResult` 函数
  - [x] SubTask 2.2: 实现 `create_delivery_branch(workspace_path, run_id) -> BranchResult` 函数
  - [x] SubTask 2.3: 实现 `generate_delivery_diff(workspace_path) -> DiffResult` 函数
  - [x] SubTask 2.4: 实现 `execute_delivery(workspace_path, run_id, goal_summary) -> DeliveryResult` 函数

- [x] Task 3: 修改 `stage_runner.py` 增强 `delivery_integration` 阶段（RC1/RC2/RC6 修复）
  - [x] SubTask 3.1: 在 `_assemble_input` 中为 `delivery_integration` 阶段添加 workspace 信息（`workspace_path`、`run_id`）和 `requirement_brief`（用于提取 goal_summary）
  - [x] SubTask 3.2: 在 `execute_stage` 中为 `delivery_integration` 阶段添加特殊处理：调用 `DeliveryService.execute_delivery()` 执行 Git 操作，生成 `delivery_manifest` artifact
  - [x] SubTask 3.3: 将 `delivery_manifest` 和 `delivery_summary` 一起保存为 artifacts

- [x] Task 4: 修改 `stage_runner.py` 在 `code_generation` 阶段生成 `diff_manifest`（RC3 修复）
  - [x] SubTask 4.1: 在 `execute_stage` 中，当 `stage_key == "code_generation"` 且阶段成功后，调用 `generate_diff(workspace_path)` 生成 diff 信息
  - [x] SubTask 4.2: 将 diff 信息保存为 `diff_manifest` artifact
  - [x] SubTask 4.3: 将 `diff_manifest` artifact ID 添加到 `output_artifact_refs`

- [x] Task 5: 修改 `orchestrator.py` Pipeline 完成时归档 Workspace（RC7 修复）
  - [x] SubTask 5.1: 在 `handle_stage_success` 中，当 PipelineRun 状态变为 `succeeded` 时，调用 `archive_workspace` 归档 workspace
  - [x] SubTask 5.2: 在 `handle_stage_failure` 中，当 PipelineRun 状态变为 `failed` 时，同样归档 workspace
  - [x] SubTask 5.3: 归档操作为 best-effort，失败仅记录 warning 日志

- [x] Task 6: 新增交付 API 路由（RC5 修复 — 远程集成基础）
  - [x] SubTask 6.1: 新建 `backend/app/api/routes_delivery.py`，实现 `GET /api/pipelines/{id}/delivery` 端点
  - [x] SubTask 6.2: 实现 `GET /api/pipelines/{id}/delivery/patch` 端点
  - [x] SubTask 6.3: 实现 `POST /api/pipelines/{id}/delivery/push` 端点
  - [x] SubTask 6.4: 实现 `POST /api/pipelines/{id}/delivery/pr` 端点
  - [x] SubTask 6.5: 在 `main.py` 中注册 delivery 路由

- [x] Task 7: 新增飞书交付通知（RC5 修复 — 飞书集成）
  - [x] SubTask 7.1: 在 `config.py` 中添加 `FEISHU_WEBHOOK_URL` 配置项
  - [x] SubTask 7.2: 新建 `backend/app/core/notification/feishu_notifier.py`
  - [x] SubTask 7.3: 在 `orchestrator.py:handle_stage_success` 中，PipelineRun 完成后调用飞书通知

- [x] Task 8: 端到端验证——产物沉淀与交付闭环
  - [x] SubTask 8.1: 验证 Pipeline 完成后 workspace 中存在交付 commit（commit message 格式正确、DevFlow 身份）
  - [x] SubTask 8.2: 验证 feature branch `devflow/{run_id[:12]}` 已创建且包含交付 commit
  - [x] SubTask 8.3: 验证 `diff_manifest` artifact 在 code_generation 阶段后正确生成
  - [x] SubTask 8.4: 验证 `delivery_manifest` artifact 包含 commit_hash、branch_name、changed_files 等字段
  - [x] SubTask 8.5: 验证 `GET /api/pipelines/{id}/delivery` 返回正确的交付信息
  - [x] SubTask 8.6: 验证 `GET /api/pipelines/{id}/delivery/patch` 返回有效的 unified diff
  - [x] SubTask 8.7: 验证 Pipeline 完成后 workspace 状态为 `archived`
  - [x] SubTask 8.8: 验证飞书通知在 Webhook 配置时正确发送，未配置时跳过

# Task Dependencies

- [Task 2] depends on [Task 1]（DeliveryManifest schema 先定义，DeliveryService 才能返回结构化结果）
- [Task 3] depends on [Task 1] + [Task 2]（delivery_integration 增强依赖 DeliveryService 和 DeliveryManifest）
- [Task 4] 可与 [Task 1-3] 并行（diff_manifest 生成独立于交付流程）
- [Task 5] 可与 [Task 1-3] 并行（workspace 归档独立于交付 Git 操作）
- [Task 6] depends on [Task 1] + [Task 3]（交付 API 依赖 delivery_manifest artifact 存在）
- [Task 7] depends on [Task 3]（飞书通知依赖交付信息可用）
- [Task 8] depends on [Task 1-7]（验证需要所有功能完成）
