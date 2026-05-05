# Tasks

- [x] Task 1: 新增 QualityGateError 异常类
  - [x] 1.1: 在 `devflow/code/agent.py` 新增 `QualityGateError` 异常类，继承自 `Exception`，包含 `stage`、`reasons`、`quality_snapshot` 属性
  - [x] 1.2: 在 `devflow/code/agent.py` 的 `validate_solution_artifact` 中，将 `ValueError("技术方案未标记为 ready_for_code_generation。")` 替换为 `QualityGateError`

- [x] Task 2: 检查点质量快照
  - [x] 2.1: 在 `devflow/checkpoint.py` 的 `build_solution_review_checkpoint` 中，从 solution artifact 读取 `quality` 字段，写入 checkpoint 的 `quality_snapshot`
  - [x] 2.2: 当 `ready_for_code_generation: false` 时，checkpoint status 设为 `waiting_approval_with_warnings`（而非 `waiting_approval`）

- [x] Task 3: 审批命令解析扩展
  - [x] 3.1: 在 `devflow/checkpoint.py` 的 `parse_checkpoint_command` 中，解析 `--force` / `强制通过` / `强制同意` / `override` 标志
  - [x] 3.2: 返回结构中增加 `force_override: bool` 字段

- [x] Task 4: 审批前就绪校验
  - [x] 4.1: 在 `devflow/checkpoint.py` 的 `apply_checkpoint_decision` 中，当 `decision == "approve"` 且 checkpoint `quality_snapshot.ready_for_code_generation == false` 时：
    - 若 `force_override == False`：阻止审批，返回包含 warnings 的提示
    - 若 `force_override == True`：允许审批，checkpoint status 设为 `approved_with_override`，记录 `override_reason` 和 `quality_at_approval`
  - [x] 4.2: 在 `devflow/pipeline.py` 的 `approve_checkpoint_run` 中，将 `force_override` 参数传递给 `apply_checkpoint_decision`

- [x] Task 5: 审批卡片质量警告展示
  - [x] 5.1: 在审批卡片模板中，当 checkpoint status 为 `waiting_approval_with_warnings` 时，增加质量警告区域
  - [x] 5.2: 展示 `quality_snapshot.warnings` 和提示文案"方案存在未决问题，建议确认后再批准。如需强制通过，请回复：Approve {run_id} --force"

- [x] Task 6: 代码生成阶段优雅失败
  - [x] 6.1: 在 `devflow/pipeline.py` 的 `run_code_generation_after_approval` 中，捕获 `QualityGateError`（而非通用 ValueError），将阶段状态设为 `failed`，运行状态正确更新为 `failed`，写入错误信息
  - [x] 6.2: 确保 `run_code_generation_after_approval` 的 except 分支正确更新 `run_payload["status"]` 和 `run_payload["lifecycle_status"]`
  - [x] 6.3: 确保 `_solution_approved_node` 中 `QualityGateError` 被妥善处理，不会导致 `run_pipeline_graph` 崩溃

- [x] Task 7: 端到端验证
  - [x] 7.1: 构造 `ready_for_code_generation: false` 的 solution artifact，验证审批被阻止
  - [x] 7.2: 验证 `--force` 审批可以通过
  - [x] 7.3: 验证代码生成阶段 `QualityGateError` 不会导致进程崩溃
  - [x] 7.4: 验证 `run.json` 状态在失败时正确反映

# Task Dependencies

- Task 2 → Task 4（审批校验依赖检查点中的质量快照）
- Task 3 → Task 4（force_override 参数来自命令解析）
- Task 1 → Task 6（QualityGateError 需要先定义才能被捕获）
- Task 4 + Task 6 → Task 7（端到端验证依赖所有功能完成）
- Task 5 独立于 Task 4/6（卡片展示可与校验逻辑并行）
