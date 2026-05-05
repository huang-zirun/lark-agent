# 代码评审审批节点 — 飞书三方审批通道实现

> 日期：2026-05-06

## 问题

代码评审检查点（检查点2）缺少飞书三方审批通道，仅支持 IM 文本命令和卡片通知，而方案设计检查点（检查点1）已完整实现三方审批。用户在代码评审阶段无法通过飞书审批应用直接「同意」或「拒绝」。

## 方案

1. 泛化 `approval_client.py` 中的审批函数，新增 `ensure_stage_approval_definition(stage)` 和 `create_stage_approval_instance(stage)`，通过 `_STAGE_APPROVAL_CONFIG` 字典映射阶段配置
2. 修改 `publish_code_review_checkpoint()` 优先尝试三方审批通道，失败降级到卡片通道
3. 修改 `approve_checkpoint_run()` 和 `reject_checkpoint_run()` 同步三方审批实例状态
4. 修改 `build_code_review_card()` 增加审批通道提示

## 修改文件

- `devflow/approval_client.py` — 新增 `_STAGE_APPROVAL_CONFIG`、`ensure_stage_approval_definition()`、`create_stage_approval_instance()`、`build_code_review_form()`
- `devflow/pipeline.py` — 新增 `_resolve_sender_id()`、`_publish_code_review_via_external_approval()`、`_sync_approval_instance_if_needed()`；修改 `publish_code_review_checkpoint()`、`approve_checkpoint_run()`、`reject_checkpoint_run()`
- `devflow/checkpoint.py` — 修改 `build_code_review_card()` 增加 `has_approval_instance` 参数
- `tests/test_approval_client.py` — 新增测试文件
- `tests/test_checkpoint.py` — 新增 `CodeReviewApprovalTests` 测试类
- `journey/design.md` — 更新设计快照
