# 第四节点（test-generation-agent）可用性验证计划

## 背景

第四个节点 `test-generation-agent` 已实现，包含以下模块：

* `devflow/test/agent.py` — LLM 工具循环 + 产物构建

* `devflow/test/models.py` — schema 常量

* `devflow/test/prompt.py` — 系统/用户提示词

* `devflow/test/runners.py` — 测试框架检测（Python/JS/Java）

* CLI 集成：`devflow test generate`

* Pipeline 集成：审批通过后自动执行 code\_generation → test\_generation

上一轮测试已生成可用产物：

* 运行目录：`artifacts/runs/20260503T175301Z-om_x100b504cf91710a0b2684bda1f50133-2347d7cf/`

* 工作区：`D:\lark\workspaces\snake-game`（含 `index.html` + `README.md`）

* 已有产物：`requirement.json`、`solution.json`、`code-generation.json`

* 但该运行中 `test_generation` 状态仍为 `pending`（测试生成节点实现前的旧运行）

## 验证步骤

### 步骤 1：运行现有单元测试

```powershell
uv run pytest tests/test_test_generation.py -q -p no:cacheprovider
```

验证 test-generation 模块的 4 个测试用例全部通过：

* `test_detects_python_pytest_and_unittest_fallback`

* `test_detects_js_and_java_test_commands_without_installing_dependencies`

* `test_test_generation_agent_writes_tests_runs_command_and_returns_artifact`

* `test_cli_generates_tests_from_explicit_artifacts`

* `test_writes_artifact_and_diff_helpers`

### 步骤 2：运行 pipeline 集成测试

```powershell
uv run pytest tests/test_pipeline_start.py::PipelineStartTests::test_approve_checkpoint_with_solution_runs_code_and_test_generation tests/test_pipeline_start.py::PipelineStartTests::test_test_generation_failure_records_test_stage_without_losing_code_artifact -q -p no:cacheprovider
```

验证审批后自动触发 code + test 生成的两个关键集成测试通过。

### 步骤 3：运行全量测试

```powershell
uv run pytest tests/test_test_generation.py tests/test_code_generation.py tests/test_pipeline_start.py -q -p no:cacheprovider
```

确保三个相关测试文件全部通过，无回归。

### 步骤 4：使用已有运行产物手动测试 `devflow test generate`

用上一轮生成的 snake-game 产物，通过 CLI 命令手动触发测试生成：

```powershell
uv run devflow test generate --run 20260503T175301Z-om_x100b504cf91710a0b2684bda1f50133-2347d7cf
```

此命令将：

1. 从 `run.json` 读取上游产物路径
2. 加载 `requirement.json`、`solution.json`、`code-generation.json`
3. 检测 `D:\lark\workspaces\snake-game` 的测试框架
4. 调用 LLM 生成测试代码
5. 写出 `test-generation.json` 和 `test.diff`

**预期问题**：

* snake-game 是纯 HTML 项目，没有 `package.json`/`pyproject.toml`/`pom.xml`，`detect_test_stack` 会返回 `language: unknown, framework: unknown, commands: []`

* 工作区没有 `.git` 目录，`capture_git_diff` 会返回空字符串

* LLM 需要配置有效的 API key（config.json 中需要填写）

### 步骤 5：验证产物完整性

检查生成的 `test-generation.json`：

* `schema_version` 为 `devflow.test_generation.v1`

* `status` 为 `success`

* `detected_stack` 包含正确的检测结果

* `generated_tests` 列出测试文件路径

* `test_commands` 记录执行的测试命令

* `tool_events` 记录工具调用历史

* `diff` 包含变更内容

### 步骤 6：编译检查

```powershell
uv run python -m compileall devflow
```

确保所有 Python 模块无语法错误。

## 风险与注意事项

1. **LLM 配置依赖**：步骤 4 和 5 需要有效的 LLM API key，如果 `config.json` 未配置或 key 过期，测试生成将失败
2. **snake-game 特殊性**：纯 HTML 项目无标准测试框架，LLM 可能生成基于浏览器的测试或手动测试说明，而非自动化测试
3. **工作区状态**：snake-game 工作区缺少 `.git`，diff 输出将为空
4. **幂等性**：如果多次运行步骤 4，后续运行会覆盖之前的 `test-generation.json`

## 验证成功标准

* [ ] 步骤 1-3 的所有单元测试和集成测试通过

* [ ] 步骤 4 的 CLI 命令成功执行并输出产物路径

* [ ] 步骤 5 的产物完整性检查通过

* [ ] 步骤 6 的编译检查通过

