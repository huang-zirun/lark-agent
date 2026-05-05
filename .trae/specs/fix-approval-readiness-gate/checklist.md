- [x] QualityGateError 异常类已定义，validate_solution_artifact 使用 QualityGateError 替代 ValueError

- [x] build_solution_review_checkpoint 在创建检查点时写入 quality_snapshot 字段

- [x] 当 ready_for_code_generation: false 时，检查点 status 为 waiting_approval_with_warnings

- [x] parse_checkpoint_command 支持 --force / 强制通过 / 强制同意 / override 标志

- [x] apply_checkpoint_decision 在方案未就绪时阻止普通审批，返回包含 warnings 的提示

- [x] apply_checkpoint_decision 在方案未就绪但 force_override=True 时允许审批，status 设为 approved_with_override

- [x] approve_checkpoint_run 将 force_override 传递给 apply_checkpoint_decision

- [x] 审批卡片在 waiting_approval_with_warnings 状态时展示质量警告和强制通过提示

- [x] run_code_generation_after_approval 捕获 QualityGateError，正确更新阶段和运行状态为 failed

- [x] _solution_approved_node 中 QualityGateError 不导致 run_pipeline_graph 崩溃

- [x] run.json 在代码生成失败时 status 和 lifecycle_status 正确反映失败状态

- [x] 端到端：ready_for_code_generation: false 时普通审批被阻止

- [x] 端到端：--force 审批可以通过并进入代码生成

- [x] 端到端：代码生成阶段 QualityGateError 不导致 devflow start 进程崩溃
