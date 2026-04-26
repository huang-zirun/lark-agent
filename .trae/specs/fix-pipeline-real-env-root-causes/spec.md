# Pipeline 真实环境测试根因修复 Spec

## Why

Pipeline 在使用豆包模型进行真实环境测试时，前两个阶段（requirement_analysis、solution_design）成功执行，但后续流程因检查点审批 API 崩溃和 artifact 保存问题而中断。这些问题不是孤立的 bug，而是系统性的契约缺失和验证缺口导致的。需要从根因层面修复，拒绝 ad-hoc patch。

## 根因分析

### RC1: API-Execution 契约不匹配（`use_mock` 参数）

- **位置**: `routes_checkpoint.py:37,60`
- **症状**: `TypeError: run_pipeline_stages() got an unexpected keyword argument 'use_mock'`
- **根因**: `run_pipeline_stages` 已重构为内部通过 `resolve_provider` + `isinstance(provider, MockProvider)` 判断是否使用 mock，但 `routes_checkpoint.py` 的调用方仍传递已废弃的 `use_mock=True` 参数
- **影响**: 检查点 approve/reject 端点完全不可用（500 错误），Pipeline 无法从 checkpoint 恢复执行

### RC2: Agent 输出契约模糊

- **位置**: `runner.py:_validate_and_fix_output`
- **症状**: `stage_runner.py` 中 `'str' object has no attribute 'get'` 错误
- **根因**: `_validate_and_fix_output` 只验证 `ARTIFACT_TYPE_TO_SCHEMA` 中已注册的 key，对未注册的 key（如 `reasoning`、`summary` 等字符串字段）原样保留在返回值中。下游消费者 `stage_runner.py` 假设所有值都是 dict
- **影响**: LLM 返回额外非 dict 字段时，阶段执行崩溃；当前 ad-hoc 修复（`isinstance` 检查）虽绕过崩溃，但未解决根本的契约问题

### RC3: 验证执行缺口

- **位置**: `stage_runner.py:76-80`
- **症状**: 不符合 schema 的 artifact 数据被持久化
- **根因**: `stage_runner.py` 中的 schema 验证仅记录 warning，不阻止无效数据保存。与 `runner.py:_validate_and_fix_output` 的强制验证形成语义不一致
- **影响**: 下游阶段读取无效 artifact 时可能崩溃

### RC4: 输出 Schema 映射硬编码

- **位置**: `runner.py:_get_output_schema:91-109`
- **症状**: 新增 agent 类型时容易遗漏映射
- **根因**: `_get_output_schema` 使用 if/elif 链将 `profile.output_schema` 映射到 artifact type，与 `ARTIFACT_TYPE_TO_SCHEMA` 是两套独立的映射逻辑
- **影响**: 映射遗漏时 LLM 调用不传递 schema 约束，输出格式完全不可控

### RC5: `ChangeSetFile.patch` Schema 语义不一致

- **位置**: `artifacts.py:34`
- **症状**: `patch` 为必填字段，但 `content` 提供时 `patch` 可为空字符串
- **根因**: Schema 未反映 `content` 和 `patch` 为互斥替代方案的实际使用模式
- **影响**: LLM 可能遗漏 `patch` 字段导致验证失败，或提供空字符串导致下游 `apply_patch` 行为异常

### RC6: Mock/真实输出一致性缺口

- **位置**: `mock_agents.py`
- **症状**: Mock 测试通过但真实 LLM 调用失败
- **根因**: Mock agent 输出绕过了 `run_agent` 的验证管道（`_validate_and_fix_output`），且 mock 输出本身未经 schema 验证
- **影响**: 测试给出虚假信心

## What Changes

- 修复 `routes_checkpoint.py` 中 `use_mock` 参数调用，移除已废弃参数
- 在 `runner.py:run_agent` 返回前过滤非 artifact key，建立明确的输出契约
- 将 `stage_runner.py` 中的 schema 验证从 advisory 提升为 enforceable（验证失败时跳过保存并记录错误）
- 统一 `_get_output_schema` 映射逻辑，基于 `ARTIFACT_TYPE_TO_SCHEMA` 配置驱动
- 修正 `ChangeSetFile.patch` 为可选字段 `str | None = None`
- 为 mock agent 输出添加 schema 验证

## Impact

- Affected specs: Checkpoint Service, Artifact Schema 校验, Agent 实现
- Affected code:
  - `backend/app/api/routes_checkpoint.py`
  - `backend/app/agents/runner.py`
  - `backend/app/core/execution/stage_runner.py`
  - `backend/app/schemas/artifacts.py`
  - `backend/app/agents/mock_agents.py`

## ADDED Requirements

### Requirement: Agent 输出契约

`run_agent` 函数 SHALL 仅返回 `ARTIFACT_TYPE_TO_SCHEMA` 中注册的 artifact key，过滤掉所有非 artifact key。

#### Scenario: LLM 返回额外字段
- **WHEN** LLM 返回 `{"requirement_brief": {...}, "reasoning": "some text"}`
- **THEN** `run_agent` 仅返回 `{"requirement_brief": {...}}`，`reasoning` 被过滤

#### Scenario: LLM 返回纯 artifact 数据
- **WHEN** LLM 返回 `{"requirement_brief": {...}, "design_spec": {...}}`
- **THEN** `run_agent` 返回 `{"requirement_brief": {...}, "design_spec": {...}}`

### Requirement: Checkpoint API 契约一致性

Checkpoint approve/reject 端点 SHALL 使用与 `run_pipeline_stages` 函数签名一致的参数调用。

#### Scenario: Approve 检查点
- **WHEN** 用户提交 Approve
- **THEN** 调用 `run_pipeline_stages(db, record.run_id)` 不传递 `use_mock` 参数
- **AND** Pipeline 从 checkpoint 恢复执行

#### Scenario: Reject 检查点
- **WHEN** 用户提交 Reject
- **THEN** 调用 `run_pipeline_stages(db, record.run_id)` 不传递 `use_mock` 参数
- **AND** Pipeline 回退到 reject_target 阶段

### Requirement: Artifact 验证强制执行

`stage_runner.py` 中的 schema 验证 SHALL 阻止不符合 schema 的 artifact 被保存。

#### Scenario: Schema 验证失败
- **WHEN** artifact 数据不符合对应的 schema
- **THEN** 跳过该 artifact 的保存
- **AND** 记录 error 级别日志
- **AND** 将该 artifact_type 记录到 `output_artifact_refs` 中标记为 `__validation_failed__`

#### Scenario: 未注册的 artifact_type
- **WHEN** artifact_type 不在 `ARTIFACT_TYPE_TO_SCHEMA` 中
- **THEN** 跳过该 artifact 的保存
- **AND** 记录 warning 级别日志

### Requirement: 输出 Schema 映射配置驱动

`_get_output_schema` SHALL 使用配置驱动的方式映射 `profile.output_schema` 到 artifact type，而非硬编码 if/elif 链。

#### Scenario: 映射查找
- **WHEN** 调用 `_get_output_schema(profile)`
- **THEN** 通过 `OUTPUT_SCHEMA_TO_ARTIFACT_TYPE` 映射表查找对应的 artifact type
- **AND** 从 `ARTIFACT_TYPE_TO_SCHEMA` 获取 schema class

#### Scenario: 映射缺失
- **WHEN** `profile.output_schema` 不在映射表中
- **THEN** 记录 warning 日志并返回 None

### Requirement: ChangeSetFile Schema 语义正确性

`ChangeSetFile.patch` SHALL 为可选字段，与 `content` 形成互斥替代方案。

#### Scenario: 使用 content 创建新文件
- **WHEN** `change_type` 为 `create` 且提供 `content`
- **THEN** `patch` 可为 None
- **AND** 下游使用 `content` 写入文件

#### Scenario: 使用 patch 修改文件
- **WHEN** `change_type` 为 `modify` 且提供 `patch`
- **THEN** `content` 可为 None
- **AND** 下游使用 `patch` 应用变更

### Requirement: Mock Agent 输出验证

Mock agent 输出 SHALL 经过与真实 agent 相同的 schema 验证。

#### Scenario: Mock agent 输出验证
- **WHEN** mock agent 返回数据
- **THEN** 数据经过 `ARTIFACT_TYPE_TO_SCHEMA` 中对应 schema 的验证
- **AND** 验证失败时抛出明确错误

## MODIFIED Requirements

### Requirement: Artifact Schema 校验

系统 SHALL 对每种 Artifact 类型进行 Schema 校验，且校验失败时阻止持久化。

原要求中 schema 校验仅为 advisory（warning），现修改为 enforceable：
- `stage_runner.py` 中 schema 验证失败时，不保存该 artifact，记录 error 日志
- `runner.py` 中 `_validate_and_fix_output` 过滤非 artifact key 后返回
- 新增 `OUTPUT_SCHEMA_TO_ARTIFACT_TYPE` 映射表统一管理 agent 输出 schema 到 artifact type 的映射

## REMOVED Requirements

无。
