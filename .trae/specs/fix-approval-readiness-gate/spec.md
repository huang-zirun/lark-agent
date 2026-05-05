# 审批门就绪校验 Spec

## Why

DevFlow 流水线存在"审批通过但产物未就绪"的状态不一致缺陷。LLM 生成的技术方案 `quality.ready_for_code_generation: false` 时，检查点仍以 `waiting_approval` 状态发送给用户审批；用户批准后，代码生成阶段的 `validate_solution_artifact` 拦截并抛出 ValueError，导致 `devflow start` 进程异常中断。已有的质量信号（`ready_for_next_stage`、`quality_gate`）未参与审批决策逻辑。

## 前因后果

### 事件链

1. 用户通过飞书发送"创建一个俄罗斯方块小游戏 夏天主题"
2. `requirement_intake` 完成，进入 `solution_design`
3. workspace 解析失败（缺少仓库上下文），状态变为 `blocked`
4. 用户补充仓库上下文，`resume_blocked_solution_design` 恢复执行
5. LLM 生成技术方案，识别出 5 个开放问题，标记 `ready_for_code_generation: false`
6. `maybe_run_solution_design` 仍创建 `waiting_approval` 检查点并发送审批卡片
7. 用户在飞书批准检查点
8. `approve_checkpoint_run` → `run_pipeline_graph(entrypoint="solution_approved")` → `run_code_generation_after_approval` → `validate_solution_artifact` 发现 `ready_for_code_generation: false`，抛出 ValueError
9. 异常未被妥善捕获，`devflow start` 进程崩溃

### 根因

三个层面的脱节：

- **质量信号与审批决策脱节**：`ready_for_code_generation` 和 `quality_gate` 不影响 `apply_checkpoint_decision("approve")` 的执行
- **审批状态与产物状态脱节**：checkpoint 状态变为 `approved`，但底层产物的 `ready_for_code_generation` 仍为 `false`
- **下游假设与上游实际脱节**：`run_code_generation_after_approval` 假设方案已就绪，但方案可能仍有未决问题

### 行业调研结论

| 模式 | 采用者 | 适用性 |
|------|--------|--------|
| 预审批验证 | MetaGPT ActionOutput、CrewAI output_pydantic | ✅ 最直接解决当前问题 |
| 审批时质量快照 | 所有有审批机制的 agent | ✅ 最小改动，可观测性提升 |
| 条件审批 | CrewAI callback、AutoGPT 分级 | ⚠️ 中期改进 |
| 审批后回滚 | Devin Git 快照、Aider /undo | ⚠️ 需要额外基础设施 |
| 下游降级 | OpenHands PAUSED 状态 | ⚠️ 长期改进 |

核心结论：**当前最大风险不是缺少复杂机制，而是已有的质量信号没有参与审批决策逻辑**。

## What Changes

- 在 `apply_checkpoint_decision` 中增加产物就绪校验：当方案 `ready_for_code_generation: false` 时，阻止自动审批通过，要求显式 override
- 在 `approve_checkpoint_run` 中增加审批前就绪校验：审批前检查方案质量状态，未就绪时返回提示而非触发下游
- 在 `maybe_run_solution_design` 中：当 `ready_for_code_generation: false` 时，检查点状态改为 `waiting_approval_with_warnings`，审批卡片中展示警告信息
- 在 `validate_solution_artifact` 中：将硬性 ValueError 改为可被上层捕获的 `QualityGateError`，提供更丰富的错误上下文
- 修复 `run.json` 状态不一致：`code_generation` 失败时 `status` 和 `lifecycle_status` 应正确反映失败状态

## Impact

- Affected specs: 审批门控机制、检查点状态模型
- Affected code:
  - `devflow/checkpoint.py` — `apply_checkpoint_decision`、`build_solution_review_checkpoint`
  - `devflow/pipeline.py` — `approve_checkpoint_run`、`maybe_run_solution_design`、`run_code_generation_after_approval`
  - `devflow/code/agent.py` — `validate_solution_artifact`

## ADDED Requirements

### Requirement: 审批前就绪校验

系统 SHALL 在执行审批决策前检查关联产物的就绪状态。当方案 `ready_for_code_generation: false` 时，审批 SHALL 被阻止，并返回包含未就绪原因的提示信息。

#### Scenario: 方案未就绪时阻止审批
- **WHEN** 用户对 `solution_design` 阶段的检查点执行 `approve`
- **AND** 关联方案的 `quality.ready_for_code_generation` 为 `false`
- **THEN** 系统 SHALL 阻止审批通过
- **AND** 返回提示信息，包含 `quality.warnings` 中的所有警告

#### Scenario: 方案未就绪时显式 override 审批
- **WHEN** 用户对 `solution_design` 阶段的检查点执行 `approve` 并附带 override 标志
- **AND** 关联方案的 `quality.ready_for_code_generation` 为 `false`
- **THEN** 系统 SHALL 允许审批通过
- **AND** 检查点中 SHALL 记录 `override_reason: "human_override_quality_gate_failed"` 和 `quality_at_approval` 快照

#### Scenario: 方案已就绪时正常审批
- **WHEN** 用户对 `solution_design` 阶段的检查点执行 `approve`
- **AND** 关联方案的 `quality.ready_for_code_generation` 不为 `false`
- **THEN** 系统 SHALL 正常执行审批流程

### Requirement: 检查点质量快照

系统 SHALL 在创建检查点时记录关联产物的质量状态，使审批者和下游消费者可以感知产物质量。

#### Scenario: 创建检查点时记录质量快照
- **WHEN** 系统为 `solution_design` 阶段创建检查点
- **THEN** 检查点 SHALL 包含 `quality_snapshot` 字段，记录 `ready_for_code_generation`、`completeness_score`、`risk_level`、`warnings` 的值

### Requirement: 审批卡片质量警告

系统 SHALL 在发送审批卡片时展示方案质量警告，使审批者做出知情决策。

#### Scenario: 方案有质量警告时展示
- **WHEN** 方案的 `quality.ready_for_code_generation` 为 `false`
- **AND** 系统发送审批卡片
- **THEN** 卡片 SHALL 包含质量警告区域，展示 `quality.warnings` 中的所有警告
- **AND** 卡片 SHALL 提示"方案存在未决问题，建议确认后再批准"

### Requirement: 代码生成校验错误可恢复

系统 SHALL 将代码生成阶段的方案校验失败视为可恢复错误，而非导致进程崩溃的异常。

#### Scenario: 方案未就绪时代码生成优雅失败
- **WHEN** `validate_solution_artifact` 发现 `ready_for_code_generation: false`
- **THEN** 系统 SHALL 抛出 `QualityGateError`（而非通用 `ValueError`）
- **AND** `run_code_generation_after_approval` SHALL 将阶段状态设为 `failed`，将运行状态正确更新为 `failed`
- **AND** 进程 SHALL NOT 崩溃，而是继续处理后续事件

## MODIFIED Requirements

### Requirement: 检查点状态模型

原模型：`waiting_approval` / `approved` / `rejected` / `awaiting_reject_reason` / `blocked`

修改为：`waiting_approval` / `waiting_approval_with_warnings` / `approved` / `approved_with_override` / `rejected` / `awaiting_reject_reason` / `blocked`

新增 `waiting_approval_with_warnings`：方案存在质量问题但仍可审批，审批卡片中展示警告。
新增 `approved_with_override`：审批时方案未就绪，审批者显式 override 质量门。

### Requirement: 审批命令解析

原命令：`Approve {run_id}` / `Reject {run_id}: 理由`

修改为：`Approve {run_id}` / `Approve {run_id} --force` / `Reject {run_id}: 理由`

新增 `--force` 标志用于覆盖质量门阻塞。中文别名：`强制通过`、`强制同意`、`override`。

## REMOVED Requirements

无移除的需求。
