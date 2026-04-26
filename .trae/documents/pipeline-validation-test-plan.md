# DevFlow Engine Pipeline 验证测试计划

## 测试目标

验证 DevFlow Engine 在使用**豆包模型**（Doubao/字节跳动大模型）时的完整 Pipeline 执行能力，记录每一步的执行情况、模型响应结果以及最终能否成功完成需求实现。

## 测试背景

### 项目架构
- **Pipeline 引擎**: 8 阶段线性流程（requirement_analysis → solution_design → checkpoint_design_approval → code_generation → test_generation_and_execution → code_review → checkpoint_final_approval → delivery_integration）
- **Agent 系统**: 6 个专用 Agent（requirement_agent, design_agent, code_patch_agent, test_agent, review_agent, delivery_agent）
- **Provider 支持**: OpenAI-compatible API（豆包模型通过此接口接入）、Anthropic、Mock
- **人工检查点**: 2 个（设计方案审批、最终代码审批）

### 豆包模型能力约束
根据用户说明，豆包模型能力较为有限，需要特别关注：
1. JSON 结构化输出稳定性
2. 代码生成质量
3. 复杂推理任务表现
4. 长上下文处理能力

## 测试需求设计

### 选择原则
根据 `journey/design.md` 第 19 节推荐，选择**简单、独立、可验证**的功能：

> 推荐第一版演示任务：为 DevFlow Engine 增加 GET /api/health 接口

### 测试需求描述

```
为 DevFlow Engine 后端添加一个健康检查接口 GET /api/health，
返回包含以下字段的 JSON 响应：
- service: 服务名称（"devflow-engine"）
- status: 状态（"ok"）
- version: 版本号（从配置读取）
- time: 当前 ISO 格式时间戳

验收标准：
1. GET /api/health 返回 HTTP 200
2. 响应 JSON 包含所有必需字段
3. 包含对应的单元测试
4. 测试通过
```

## 测试执行计划

### 阶段 1: 环境准备

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1.1 | 配置豆包模型 Provider | 在数据库中创建 ProviderConfig，类型为 OPENAI，api_base 指向豆包 API |
| 1.2 | 验证 Provider 连接 | 调用 validate() 返回 True |
| 1.3 | 注册 Workspace | 将当前代码库注册为 workspace |
| 1.4 | 创建 PipelineRun | 使用上述需求文本创建 run，状态为 draft |
| 1.5 | 执行预检 | 状态变为 ready |

### 阶段 2: Pipeline 执行

#### Stage 1: requirement_analysis（需求分析 Agent）

**输入**: requirement_text
**预期输出**: requirement_brief（结构化需求文档）

**验证要点**:
- [ ] Agent 是否正确理解需求
- [ ] 是否正确提取 goal、acceptance_criteria、constraints
- [ ] JSON 输出格式是否合规
- [ ] 模型响应时间
- [ ] Token 消耗

**记录项**:
```json
{
  "stage": "requirement_analysis",
  "model": "doubao-model-name",
  "latency_ms": 0,
  "tokens": {"prompt": 0, "completion": 0, "total": 0},
  "output_valid": true/false,
  "output_quality": "评估输出质量",
  "issues": ["如果有问题记录在此"]
}
```

#### Stage 2: solution_design（方案设计 Agent）

**输入**: requirement_brief + code_context
**预期输出**: design_spec（技术方案）

**验证要点**:
- [ ] 是否正确识别需要修改的文件
- [ ] 是否提出合理的 API 设计
- [ ] 是否考虑测试策略
- [ ] JSON 输出格式是否合规

**记录项**:
```json
{
  "stage": "solution_design",
  "affected_files_identified": ["文件列表"],
  "design_quality": "评估",
  "issues": []
}
```

#### Stage 3: checkpoint_design_approval（人工检查点）

**操作**: 人工审查 design_spec，决定是否 Approve

**验证要点**:
- [ ] 检查点是否正确触发
- [ ] UI/API 是否正确展示设计文档
- [ ] Approve 后是否正确流转到 code_generation

**记录项**:
```json
{
  "checkpoint": "design_approval",
  "decision": "approved/rejected",
  "reason": "决策理由",
  "transition_correct": true/false
}
```

#### Stage 4: code_generation（代码生成 Agent）

**输入**: design_spec + code_context
**预期输出**: change_set（代码变更集，包含 unified diff）

**验证要点**（豆包模型关键验证点）:
- [ ] 是否能正确生成 FastAPI 路由代码
- [ ] 生成的代码语法是否正确
- [ ] Patch 格式是否符合 unified diff 规范
- [ ] Patch 是否能成功应用到 workspace
- [ ] 生成的代码是否符合 Python 代码规范

**记录项**:
```json
{
  "stage": "code_generation",
  "code_quality": "评估",
  "patch_apply_success": true/false,
  "syntax_valid": true/false,
  "generated_files": ["文件列表"],
  "issues": []
}
```

#### Stage 5: test_generation_and_execution（测试生成与执行）

**输入**: change_set + requirement_brief + design_spec
**预期输出**: test_report

**验证要点**:
- [ ] 是否能生成针对 health 接口的测试
- [ ] 测试代码是否能正确写入 workspace
- [ ] 测试命令是否能正常执行
- [ ] 测试结果是否符合预期

**记录项**:
```json
{
  "stage": "test_generation_and_execution",
  "tests_generated": true/false,
  "test_files": ["文件列表"],
  "test_execution": {
    "exit_code": 0,
    "passed": 0,
    "failed": 0
  }
}
```

#### Stage 6: code_review（代码评审 Agent）

**输入**: design_spec + change_set + test_report
**预期输出**: review_report

**验证要点**:
- [ ] 是否正确评估代码正确性
- [ ] 是否正确评估安全性
- [ ] 是否正确评估代码规范
- [ ] 是否正确评估测试覆盖
- [ ] 最终建议是否合理

**记录项**:
```json
{
  "stage": "code_review",
  "recommendation": "approve/reject/needs_improvement",
  "scores": {
    "correctness": 0,
    "security": 0,
    "style": 0,
    "test_coverage": 0
  }
}
```

#### Stage 7: checkpoint_final_approval（最终人工检查点）

**操作**: 人工审查所有产物，决定是否 Approve

**验证要点**:
- [ ] 是否能查看完整的变更 diff
- [ ] 是否能查看测试报告
- [ ] 是否能查看评审报告
- [ ] Approve 后是否正确流转到 delivery_integration

#### Stage 8: delivery_integration（交付集成 Agent）

**输入**: change_set + review_report + test_report
**预期输出**: delivery_summary

**验证要点**:
- [ ] 是否正确汇总交付物
- [ ] 是否正确总结测试结果
- [ ] 是否正确识别已知风险

## 预期结果与成功标准

### 成功标准

1. **Pipeline 完成度**: 所有 8 个阶段成功执行完成
2. **代码质量**: 生成的代码能通过语法检查
3. **测试通过**: 生成的测试能成功执行
4. **功能正确**: health 接口能正常响应
5. **人工检查点**: 2 个检查点都能正常审批

### 降级预期（考虑豆包模型能力限制）

如果豆包模型在某些阶段表现不佳，记录以下降级情况：

| 场景 | 降级处理 | 记录方式 |
|------|----------|----------|
| JSON 输出格式错误 | 使用自动修复机制 | 记录修复前后的对比 |
| 代码生成语法错误 | 记录错误类型和频率 | 保存原始输出 |
| Patch 应用失败 | 记录失败原因 | 保存 patch 内容 |
| 测试生成不完整 | 记录覆盖度 | 保存测试代码 |

## 数据收集模板

### 每次 LLM 调用记录

```json
{
  "timestamp": "ISO时间",
  "stage": "阶段名称",
  "agent": "agent名称",
  "model": "模型名称",
  "request": {
    "prompt_tokens": 0,
    "prompt_preview": "前200字符"
  },
  "response": {
    "completion_tokens": 0,
    "latency_ms": 0,
    "raw_output": "原始输出",
    "parsed_output": "解析后的JSON"
  },
  "validation": {
    "passed": true/false,
    "auto_fixed": true/false,
    "error_message": "错误信息"
  }
}
```

### 阶段执行记录

```json
{
  "stage_key": "阶段标识",
  "status": "succeeded/failed/retrying",
  "attempt": 1,
  "started_at": "时间",
  "ended_at": "时间",
  "duration_ms": 0,
  "input_artifacts": ["输入产物ID"],
  "output_artifacts": ["输出产物ID"],
  "error_message": "错误信息"
}
```

## 风险评估

### 高风险项

1. **豆包模型 JSON 输出稳定性**: 可能频繁输出格式错误的 JSON
2. **代码生成质量**: 可能生成语法错误的 Python 代码
3. **Patch 格式**: 可能生成无法应用的 unified diff

### 缓解措施

1. 启用 output validation 和 auto-fix 机制
2. 设置合理的重试次数（最多 3 次）
3. 准备 Mock Agent 作为 fallback
4. 详细记录每次失败的原因

## 测试报告结构

测试完成后生成以下报告：

```
pipeline-validation-report/
├── summary.md              # 总体摘要
├── timeline.json           # 执行时间线
├── llm-calls/              # 每次 LLM 调用详情
│   ├── requirement_analysis.json
│   ├── solution_design.json
│   ├── code_generation.json
│   ├── test_generation.json
│   └── code_review.json
├── artifacts/              # 各阶段产物
│   ├── requirement_brief.json
│   ├── design_spec.json
│   ├── change_set.json
│   ├── test_report.json
│   ├── review_report.json
│   └── delivery_summary.json
└── generated-code/         # 最终生成的代码
    ├── health_endpoint.py
    └── test_health.py
```

## 执行命令参考

```powershell
# 1. 启动后端服务
uv run uvicorn app.main:app --reload

# 2. 创建 Provider（豆包模型）
# POST /api/providers
{
  "name": "豆包模型",
  "provider_type": "openai",
  "api_base": "https://ark.cn-beijing.volces.com/api/v3",
  "api_key": "YOUR_DOUBAO_API_KEY",
  "default_model": "doubao-pro-32k-241215"
}

# 3. 注册 Workspace
# POST /api/workspaces
{
  "source_repo_path": "d:\进阶指南\lark-agent",
  "name": "lark-agent-dev"
}

# 4. 创建 PipelineRun
# POST /api/pipelines
{
  "requirement_text": "为 DevFlow Engine 后端添加一个健康检查接口 GET /api/health...",
  "workspace_id": "workspace-id"
}

# 5. 启动 Pipeline
# POST /api/pipelines/{run_id}/start

# 6. 查询状态
# GET /api/pipelines/{run_id}/timeline
```

## 结论预期

本测试将验证以下关键问题：

1. ✅/❌ 豆包模型是否能稳定输出符合 Schema 的 JSON
2. ✅/❌ 豆包模型是否能生成语法正确的 Python 代码
3. ✅/❌ 豆包模型是否能生成可应用的 unified diff
4. ✅/❌ Pipeline 状态机是否能正确处理各阶段流转
5. ✅/❌ 人工检查点是否能正常工作
6. ✅/❌ 完整流程是否能成功跑通

---

*测试计划创建时间: 2026-04-26*
*测试执行人: AI Agent*
*目标模型: 豆包模型 (Doubao)*
