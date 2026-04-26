# Tasks

- [x] Task 1: 修复 `routes_checkpoint.py` 中 `use_mock` 参数调用
  - [x] SubTask 1.1: 移除第 37 行 `run_pipeline_stages(db, record.run_id, use_mock=True)` 中的 `use_mock=True`
  - [x] SubTask 1.2: 移除第 60 行 `run_pipeline_stages(db, record.run_id, use_mock=True)` 中的 `use_mock=True`
  - [x] SubTask 1.3: 验证 `run_pipeline_stages` 函数签名确认无 `use_mock` 参数

- [x] Task 2: 建立 `run_agent` 输出契约——过滤非 artifact key
  - [x] SubTask 2.1: 在 `runner.py:_validate_and_fix_output` 返回前，过滤掉不在 `ARTIFACT_TYPE_TO_SCHEMA` 中的 key
  - [x] SubTask 2.2: 添加日志记录被过滤的 key（info 级别）
  - [x] SubTask 2.3: 移除 `stage_runner.py` 中的 `isinstance(artifact_data, dict)` ad-hoc 检查（因上游已保证输出仅含 dict 值）

- [x] Task 3: 将 `stage_runner.py` 中 schema 验证从 advisory 提升为 enforceable
  - [x] SubTask 3.1: schema 验证失败时，跳过该 artifact 保存，记录 error 日志
  - [x] SubTask 3.2: 未注册 artifact_type 时，跳过保存，记录 warning 日志
  - [x] SubTask 3.3: 在 `output_artifact_refs` 中标记验证失败的 artifact 为 `__validation_failed__`

- [x] Task 4: 统一 `_get_output_schema` 映射逻辑
  - [x] SubTask 4.1: 在 `artifacts.py` 中新增 `OUTPUT_SCHEMA_TO_ARTIFACT_TYPE` 映射表
  - [x] SubTask 4.2: 重构 `runner.py:_get_output_schema` 使用映射表替代 if/elif 链
  - [x] SubTask 4.3: 映射缺失时记录 warning 日志并返回 None

- [x] Task 5: 修正 `ChangeSetFile.patch` Schema
  - [x] SubTask 5.1: 将 `artifacts.py` 中 `ChangeSetFile.patch` 从 `patch: str` 改为 `patch: str | None = None`
  - [x] SubTask 5.2: 更新 `stage_runner.py:_execute_test_stage` 中 `apply_patch` 调用，检查 `patch` 非 None 后再调用
  - [x] SubTask 5.3: 更新 `mock_agents.py` 中 `mock_code_patch_agent` 的 `test_health.py` 条目，将 `"patch": ""` 改为 `"patch": None`

- [x] Task 6: 为 mock agent 输出添加 schema 验证
  - [x] SubTask 6.1: 在 `mock_agents.py` 中新增 `validate_mock_output` 函数，对 mock agent 返回值进行 schema 验证
  - [x] SubTask 6.2: 在每个 mock agent 函数返回前调用 `validate_mock_output`
  - [x] SubTask 6.3: 验证失败时抛出 `OutputValidationError`

# Task Dependencies

- [Task 2] depends on [Task 4]（映射表先建立，过滤逻辑才能正确引用）
- [Task 3] depends on [Task 2]（上游过滤后，stage_runner 的验证逻辑才简化）
- [Task 5] 可与 [Task 1-4] 并行
- [Task 6] 可与 [Task 1-4] 并行
