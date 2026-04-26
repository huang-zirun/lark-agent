# Pipeline 流程控制与检查点审批机制深度分析 Spec

## Why

用户在前端界面完成需求输入并创建 pipeline 后，系统在第一个检查点（checkpoint_design_approval）无法通过 approve 操作实现手动推进流程。经深度代码分析，发现该问题不是单一 bug，而是由同步阻塞执行模型、事务边界过大、检查点状态管理缺失、前端轮询不可见中间状态等多个系统性缺陷叠加导致。需要从架构层面修复，拒绝 ad-hoc patch。

## 根因分析

### RC1: 同步阻塞执行模型——Pipeline 在 HTTP 请求上下文中同步运行（CRITICAL）

- **位置**: `routes_checkpoint.py:37`, `routes_pipeline.py:73`
- **症状**: 用户点击 Approve 后，前端显示 "Failed to approve" 或长时间无响应
- **根因**: `approve_checkpoint_endpoint` 调用 `run_pipeline_stages(db, record.run_id)` 同步执行所有后续阶段。每个阶段可能涉及 LLM API 调用（30-120秒），整个请求可能持续数分钟。前端 axios 超时为 30 秒，必然超时
- **影响**:
  1. 前端超时后显示 "Failed to approve"，但后端可能仍在处理
  2. 用户可能重复点击 Approve，但 checkpoint 已被批准，导致 400 错误
  3. 用户体验极差——无法得知实际执行状态

**代码路径**:
```
CheckpointPanel.handleApprove()
  → checkpointApi.approve(id)           // POST /api/checkpoints/{id}/approve
    → approve_checkpoint(db, id)         // 更新状态为 RUNNING，设置 current_stage_key
    → run_pipeline_stages(db, run_id)    // 同步执行所有后续阶段（阻塞！）
      → execute_stage(code_generation)   // LLM 调用，可能 60s+
      → execute_stage(test_stage)        // LLM 调用 + 测试执行，可能 120s+
      → execute_stage(code_review)       // LLM 调用，可能 60s+
      → ...直到下一个 checkpoint 或完成
    → return response                    // 数分钟后才返回
```

### RC2: 数据库事务边界过大——整个 Pipeline 执行在单一事务中（CRITICAL）

- **位置**: `db/session.py:18-25`, `routes_checkpoint.py:29-43`
- **症状**: 前端轮询（3秒间隔）始终看不到中间状态变化
- **根因**: `get_db` 依赖在请求结束时才 commit。`run_pipeline_stages` 执行期间，所有 `session.flush()` 的数据对其他连接不可见。前端轮询读到的始终是 approve 之前的状态
- **影响**:
  1. 前端 3 秒轮询完全无效——看不到任何进度
  2. 如果请求中途失败（超时、崩溃），所有阶段执行结果丢失
  3. 用户无法判断 pipeline 是否在运行

**代码证据**:
```python
# db/session.py
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()  # 只在请求结束时 commit
        except Exception:
            await session.rollback()
            raise
```

### RC3: 检查点 StageRun 状态从未更新（MEDIUM）

- **位置**: `executor.py:33-34`, `orchestrator.py:130-135`
- **症状**: 前端无法正确识别当前活跃的检查点
- **根因**: `run_pipeline_stages` 中 checkpoint 类型阶段被 `continue` 跳过，StageRun 永远保持 PENDING 状态。`handle_stage_success` 创建 CheckpointRecord 但不更新对应 StageRun
- **影响**:
  1. 前端 `pendingCheckpointStage` 逻辑（查找第一个 PENDING 的 checkpoint StageRun）在第二个检查点时会错误匹配到第一个检查点
  2. 第二个检查点显示的 artifacts 类型错误（显示 requirement_brief/design_spec 而非 change_set/review_report/test_report）

**代码证据**:
```python
# executor.py:33-34 — checkpoint 阶段被跳过，StageRun 状态不变
for stage_def in stage_defs:
    if stage_def.stage_type == "checkpoint":
        continue  # StageRun 永远是 PENDING

# DevWorkspace.tsx:52-54 — 前端查找第一个 PENDING 的 checkpoint
const pendingCheckpointStage = stages
    .filter((s) => s.stage_key.startsWith('checkpoint_'))
    .find((s) => s.status === 'running' || s.status === 'pending')
    // 永远找到 checkpoint_design_approval（第一个 PENDING 的）
```

### RC4: 重试机制完全失效（HIGH）

- **位置**: `executor.py:53-56`, `orchestrator.py:158-168`
- **症状**: 阶段失败后 pipeline 卡在 RUNNING 状态，无法继续也无法恢复
- **根因**: `handle_stage_failure` 将 StageRun 状态设为 RUNNING（经由 RETRYING），但 `run_pipeline_stages` 的循环在 `handle_stage_failure` 后 `break` 退出，不再重新执行该阶段。PipelineRun 状态保持 RUNNING 但无人在执行
- **影响**:
  1. 阶段失败后 pipeline 永久卡住
  2. 用户尝试 resume 时，`execute_stage` 尝试 RUNNING→RUNNING 转换，抛出 StateTransitionError
  3. 唯一恢复方式是 terminate

**代码证据**:
```python
# executor.py:53-56 — 失败后直接 break，不重试
except Exception as e:
    await handle_stage_failure(session, run_id, stage_def.key, str(e))
    break  # 退出循环，不再执行

# orchestrator.py:158-168 — 设置了 RETRYING→RUNNING 但没有重新执行
if stage_run and stage_run.attempt < 3:
    stage_run.status = RETRYING → RUNNING  # 状态改为 RUNNING
    stage_run.attempt += 1
    await asyncio.sleep(delay)  # 等待但之后直接返回
    # 没有重新执行该阶段的代码！
```

### RC5: 前端静默吞没关键错误（MEDIUM）

- **位置**: `DevWorkspace.tsx:29`, `RequirementInput.tsx:26-29`
- **症状**: 用户看不到真实错误信息，无法诊断问题
- **根因**:
  1. `checkpointApi.getPending` 的 `.catch(() => ({ data: null }))` 将所有错误静默吞没
  2. `pipelineApi.start` 的 catch 块注释 "Pipeline may stop at checkpoint, which is expected" 但也吞没了真实错误
- **影响**: 用户无法区分"预期行为"和"真实错误"，approve 失败时无任何诊断信息

### RC6: 前端检查点 artifacts 展示逻辑依赖错误的 StageRun 状态（MEDIUM）

- **位置**: `DevWorkspace.tsx:52-62`
- **症状**: 第二个检查点显示错误的 artifacts
- **根因**: `checkpointArtifacts` 的计算依赖 `pendingCheckpointStage`，而 `pendingCheckpointStage` 使用 StageRun 状态判断。由于 RC3，第一个 checkpoint StageRun 永远是 PENDING，导致第二个检查点时仍匹配到第一个
- **影响**: 最终审批时用户看到的是需求简报和设计规格，而非代码变更和测试报告

### RC7: `run_pipeline_stages` 不从 `current_stage_key` 开始执行（LOW）

- **位置**: `executor.py:32-46`
- **症状**: 每次调用都从头遍历所有阶段定义
- **根因**: 函数通过 `stage_runs` 字典跳过已成功的阶段，而非从 `current_stage_key` 开始。功能上正确但效率低，且在边缘情况下（StageRun 状态不一致时）可能产生意外行为
- **影响**: 低效但功能正确

## What Changes

- 将 `run_pipeline_stages` 改为异步后台任务执行，approve/reject API 立即返回
- 在每个阶段执行完成后立即 commit 事务，使前端轮询可见中间状态
- 为 checkpoint StageRun 添加状态转换（PENDING→RUNNING→SUCCEEDED/FAILED）
- 修复重试机制：失败后重新执行阶段而非 break 退出
- 修复前端 `pendingCheckpointStage` 逻辑，使用 `pendingCheckpoint` API 返回的数据而非 StageRun 状态
- 修复前端错误处理，不再静默吞没关键错误
- 修复前端 `checkpointArtifacts` 计算，基于 `pendingCheckpoint.stage_key` 而非 StageRun 状态

## Impact

- Affected specs: Pipeline 执行模型, Checkpoint 状态管理, 前端状态管理
- Affected code:
  - `backend/app/api/routes_checkpoint.py` — 改为后台任务
  - `backend/app/api/routes_pipeline.py` — 改为后台任务
  - `backend/app/core/execution/executor.py` — 添加中间 commit，修复重试
  - `backend/app/core/pipeline/orchestrator.py` — 更新 checkpoint StageRun 状态
  - `backend/app/db/session.py` — 添加 commit 辅助函数
  - `frontend/src/pages/DevWorkspace.tsx` — 修复检查点逻辑和错误处理
  - `frontend/src/components/CheckpointPanel.tsx` — 改进错误反馈

## ADDED Requirements

### Requirement: 异步后台执行 Pipeline 阶段

Checkpoint approve/reject 端点 SHALL 在更新检查点状态后立即返回 HTTP 响应，将后续阶段执行委托给后台任务。

#### Scenario: Approve 检查点后立即返回
- **WHEN** 用户提交 Approve
- **THEN** API 立即返回 200，CheckpointRecord 状态为 approved
- **AND** 后台任务开始执行后续阶段
- **AND** 前端通过轮询看到阶段逐步推进

#### Scenario: 后台任务执行失败
- **WHEN** 后台任务中阶段执行失败
- **THEN** PipelineRun 状态更新为 failed
- **AND** 前端轮询可见失败状态和错误信息

### Requirement: 阶段执行中间 Commit

每个阶段执行完成后 SHALL 立即 commit 数据库事务，使前端轮询可见中间状态。

#### Scenario: 阶段成功后前端可见
- **WHEN** code_generation 阶段执行成功
- **THEN** 前端 3 秒内轮询可见该阶段状态为 succeeded
- **AND** 可见该阶段产生的 artifacts

#### Scenario: 阶段失败后前端可见
- **WHEN** code_generation 阶段执行失败
- **THEN** 前端 3 秒内轮询可见该阶段状态为 failed
- **AND** 可见错误信息

### Requirement: Checkpoint StageRun 状态转换

Checkpoint 类型的 StageRun SHALL 有正确的状态转换：进入检查点时 PENDING→RUNNING，审批后 RUNNING→SUCCEEDED。

#### Scenario: Pipeline 到达检查点
- **WHEN** 前一阶段成功后下一阶段为 checkpoint
- **THEN** 对应 StageRun 状态更新为 RUNNING
- **AND** PipelineRun 状态更新为 waiting_checkpoint

#### Scenario: 检查点被批准
- **WHEN** 用户 Approve 检查点
- **THEN** 对应 StageRun 状态更新为 SUCCEEDED
- **AND** PipelineRun 状态更新为 running

#### Scenario: 检查点被拒绝
- **WHEN** 用户 Reject 检查点
- **THEN** 对应 StageRun 状态更新为 FAILED
- **AND** 回退目标 StageRun 状态重置为 PENDING

### Requirement: 有效的阶段重试机制

阶段执行失败且重试次数未耗尽时 SHALL 重新执行该阶段，而非退出循环。

#### Scenario: 阶段失败后自动重试
- **WHEN** 阶段执行失败且 attempt < 3
- **THEN** 等待指数退避延迟后重新执行该阶段
- **AND** 前端可见 retrying 状态

#### Scenario: 重试次数耗尽
- **WHEN** 阶段执行失败且 attempt >= 3
- **THEN** PipelineRun 状态更新为 failed
- **AND** StageRun 状态更新为 failed

### Requirement: 前端基于 CheckpointRecord 判断活跃检查点

前端 SHALL 使用 `pendingCheckpoint` API 返回的 CheckpointRecord 来确定当前活跃检查点，而非通过 StageRun 状态推断。

#### Scenario: 第一个检查点等待审批
- **WHEN** pendingCheckpoint 的 stage_key 为 checkpoint_design_approval
- **THEN** 显示 requirement_brief 和 design_spec artifacts
- **AND** 显示 Approve/Reject 按钮

#### Scenario: 第二个检查点等待审批
- **WHEN** pendingCheckpoint 的 stage_key 为 checkpoint_final_approval
- **THEN** 显示 change_set、review_report、test_report artifacts
- **AND** 显示 Approve/Reject 按钮

### Requirement: 前端错误可见性

前端 SHALL 向用户展示关键 API 错误，而非静默吞没。

#### Scenario: 获取 pending checkpoint 失败
- **WHEN** `checkpointApi.getPending` 请求失败
- **THEN** 显示错误提示信息
- **AND** 不将 pendingCheckpoint 设为 null（保留上次有效值或显示重试按钮）

#### Scenario: Pipeline 启动失败
- **WHEN** `pipelineApi.start` 请求失败且非超时
- **THEN** 显示错误提示信息
- **AND** 不自动导航到 workspace 页面

## MODIFIED Requirements

### Requirement: Pipeline 执行模型

原要求中 Pipeline 在 HTTP 请求上下文中同步执行，现修改为异步后台执行：
- approve/reject API 立即返回，后台任务执行后续阶段
- 每个阶段完成后 commit 事务，前端轮询可见中间状态
- 后台任务使用独立的数据库 session

### Requirement: Checkpoint StageRun 状态管理

原要求中 checkpoint StageRun 状态永远为 PENDING，现修改为有完整状态转换：
- 进入检查点：PENDING → RUNNING
- 审批通过：RUNNING → SUCCEEDED
- 审批拒绝：RUNNING → FAILED

## REMOVED Requirements

无。
