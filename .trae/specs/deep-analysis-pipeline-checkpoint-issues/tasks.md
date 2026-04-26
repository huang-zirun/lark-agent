# Tasks

- [x] Task 1: 将 Pipeline 执行改为异步后台任务（RC1 + RC2 核心修复）
  - [x] SubTask 1.1: 在 `db/session.py` 中添加 `get_background_session` 上下文管理器，用于后台任务获取独立 session 并支持中间 commit
  - [x] SubTask 1.2: 在 `executor.py` 中重构 `run_pipeline_stages`，每个阶段执行完成后调用 `session.commit()` 使前端轮询可见
  - [x] SubTask 1.3: 在 `routes_checkpoint.py` 中将 `run_pipeline_stages` 调用改为 `asyncio.create_task` 后台执行，approve/reject API 立即返回
  - [x] SubTask 1.4: 在 `routes_pipeline.py` 中将 `run_pipeline_stages` 调用同样改为后台执行（start 和 resume 端点）
  - [x] SubTask 1.5: 后台任务使用独立的数据库 session，避免与请求 session 冲突

- [x] Task 2: 修复 Checkpoint StageRun 状态转换（RC3 修复）
  - [x] SubTask 2.1: 在 `orchestrator.py:handle_stage_success` 中，当下一阶段为 checkpoint 时，更新对应 StageRun 状态为 RUNNING
  - [x] SubTask 2.2: 在 `checkpoint_service.py:approve_checkpoint` 中，更新对应 StageRun 状态为 SUCCEEDED
  - [x] SubTask 2.3: 在 `checkpoint_service.py:reject_checkpoint` 中，更新对应 StageRun 状态为 FAILED
  - [x] SubTask 2.4: 验证 StageRunStateMachine 支持 PENDING→RUNNING 和 RUNNING→SUCCEEDED/FAILED 转换（添加 RETRYING→PENDING 转换）

- [x] Task 3: 修复阶段重试机制（RC4 修复）
  - [x] SubTask 3.1: 在 `executor.py:run_pipeline_stages` 中，将 `handle_stage_failure` 后的 `break` 改为条件判断：如果 StageRun 状态为 RUNNING（重试中），继续循环重新执行该阶段
  - [x] SubTask 3.2: 在 `orchestrator.py:handle_stage_failure` 中，重试时设置 StageRun 状态为 RETRYING 然后 PENDING（而非 RUNNING），使 `execute_stage` 的 PENDING→RUNNING 转换有效
  - [x] SubTask 3.3: 添加重试延迟逻辑到 `run_pipeline_stages` 循环中（从 `handle_stage_failure` 移出）

- [x] Task 4: 修复前端检查点状态判断逻辑（RC3 + RC6 修复）
  - [x] SubTask 4.1: 在 `DevWorkspace.tsx` 中，将 `pendingCheckpointStage` 的计算改为基于 `pendingCheckpoint.stage_key` 而非 StageRun 状态
  - [x] SubTask 4.2: 修复 `checkpointArtifacts` 计算，使用 `pendingCheckpoint.stage_key` 确定展示哪些 artifacts
  - [x] SubTask 4.3: 移除对 `pendingCheckpointStage` 的依赖，直接使用 `pendingCheckpoint` 数据

- [x] Task 5: 修复前端错误处理（RC5 修复）
  - [x] SubTask 5.1: 在 `DevWorkspace.tsx` 中，`checkpointApi.getPending` 失败时显示错误提示而非静默吞没
  - [x] SubTask 5.2: 在 `RequirementInput.tsx` 中，区分 `pipelineApi.start` 的超时错误和真实错误，真实错误需展示给用户
  - [x] SubTask 5.3: 在 `CheckpointPanel.tsx` 中，approve/reject 失败时展示后端返回的具体错误信息

- [x] Task 6: 端到端验证——不通过 API 调用验证流程正确性
  - [x] SubTask 6.1: 编写 Python 脚本，直接调用后端 service 层函数模拟完整 pipeline 流程（创建→启动→等待检查点→批准→继续→完成）
  - [x] SubTask 6.2: 验证每个阶段完成后数据库状态正确（StageRun 状态、Artifact 保存、PipelineRun 状态）
  - [x] SubTask 6.3: 验证 checkpoint approve 后 pipeline 正确推进到下一阶段
  - [x] SubTask 6.4: 验证 checkpoint reject 后 pipeline 正确回退到目标阶段
  - [x] SubTask 6.5: 验证重试机制在阶段失败时正确工作

# Task Dependencies

- [Task 2] depends on [Task 1]（后台任务模型先建立，checkpoint 状态更新才能在独立事务中 commit）
- [Task 3] depends on [Task 1]（重试机制需要新的执行循环结构）
- [Task 4] 可与 [Task 1-3] 并行（纯前端修改）
- [Task 5] 可与 [Task 1-3] 并行（纯前端修改）
- [Task 6] depends on [Task 1-3]（验证需要所有后端修复完成）
