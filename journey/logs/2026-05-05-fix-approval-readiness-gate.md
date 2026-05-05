# 审批门就绪校验修复

## 问题描述

DevFlow 流水线存在"审批通过但产物未就绪"的状态不一致缺陷。当 LLM 生成的技术方案标记 `ready_for_code_generation: false` 时，检查点仍以 `waiting_approval` 状态发送给用户审批；用户批准后，代码生成阶段 `validate_solution_artifact` 抛出 `ValueError`，导致 `devflow start` 进程异常中断。

## 根因分析

三个层面的脱节：
1. **质量信号与审批决策脱节**：`ready_for_code_generation` 和 `quality_gate` 不影响 `apply_checkpoint_decision("approve")` 的执行
2. **审批状态与产物状态脱节**：checkpoint 状态变为 `approved`，但底层产物的 `ready_for_code_generation` 仍为 `false`
3. **下游假设与上游实际脱节**：`run_code_generation_after_approval` 假设方案已就绪，但方案可能仍有未决问题

## 行业调研结论

| 模式 | 采用者 | 适用性 |
|------|--------|--------|
| 预审批验证 | MetaGPT ActionOutput、CrewAI output_pydantic | ✅ 最直接解决当前问题 |
| 审批时质量快照 | 所有有审批机制的 agent | ✅ 最小改动，可观测性提升 |
| 条件审批 | CrewAI callback、AutoGPT 分级 | ⚠️ 中期改进 |
| 审批后回滚 | Devin Git 快照、Aider /undo | ⚠️ 需要额外基础设施 |

核心结论：**当前最大风险不是缺少复杂机制，而是已有的质量信号没有参与审批决策逻辑**。

## 修复方案

### 新增/修改的组件

1. **QualityGateError 异常类** (`devflow/code/agent.py`)
   - 继承自 `Exception`，包含 `stage`、`reasons`、`quality_snapshot` 属性
   - `validate_solution_artifact` 使用 `QualityGateError` 替代 `ValueError`

2. **检查点质量快照** (`devflow/checkpoint.py`)
   - `build_solution_review_checkpoint` 增加 `quality_snapshot` 字段
   - 当 `ready_for_code_generation: false` 时，状态设为 `waiting_approval_with_warnings`

3. **审批命令解析扩展** (`devflow/checkpoint.py`)
   - `CheckpointCommand` 增加 `force_override: bool` 字段
   - `parse_checkpoint_command` 支持 `--force` / `强制通过` / `强制同意` / `override` 标志

4. **审批前就绪校验** (`devflow/checkpoint.py`, `devflow/pipeline.py`)
   - `apply_checkpoint_decision` 在方案未就绪时阻止普通审批
   - `force_override=True` 时允许审批，状态设为 `approved_with_override`，记录 `override_reason` 和 `quality_at_approval`

5. **审批卡片质量警告** (`devflow/checkpoint.py`)
   - 当 `ready_for_code_generation: false` 时，卡片 header 变为橙色，标题显示"有质量警告"
   - 展示 `quality_snapshot.warnings` 和 `--force` 提示

6. **代码生成阶段优雅失败** (`devflow/pipeline.py`, `devflow/graph_runner.py`)
   - `run_code_generation_after_approval` 捕获 `QualityGateError`，正确更新阶段和运行状态为 `failed`
   - `_solution_approved_node` 安全捕获 `QualityGateError`，不导致 `run_pipeline_graph` 崩溃

## 修改文件清单

- `devflow/code/agent.py` — QualityGateError 异常类
- `devflow/checkpoint.py` — 质量快照、命令解析、审批校验、卡片渲染
- `devflow/pipeline.py` — 审批流程、代码生成错误处理
- `devflow/graph_runner.py` — 节点错误处理
- `devflow/cli.py` — CLI --force 参数

## 验证结果

- 163 个现有测试全部通过
- 5 个端到端场景验证全部通过：
  1. `ready_for_code_generation: false` 阻止普通审批 ✅
  2. `QualityGateError` 正确抛出 ✅
  3. `--force` 命令解析 ✅
  4. 审批卡片展示质量警告 ✅
  5. 方案就绪时正常审批 ✅

## 相关 Spec

- `.trae/specs/fix-approval-readiness-gate/spec.md`
- `.trae/specs/fix-approval-readiness-gate/tasks.md`
- `.trae/specs/fix-approval-readiness-gate/checklist.md`
