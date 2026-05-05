# 计划：将 Karpathy 编码指南集成到 DevFlow 所有 Coding Agent

## 背景

Karpathy 指南源自 Andrej Karpathy 对 LLM 编码陷阱的观察，包含四个核心原则：

| 原则 | 解决什么问题 |
|------|-------------|
| 编码前思考 | 错误假设、隐藏困惑、缺少权衡 |
| 简洁优先 | 过度复杂、臃肿抽象 |
| 精准修改 | 无关编辑、触碰不应碰的代码 |
| 目标驱动执行 | 缺乏可验证的成功标准 |

当前项目已有 `karpathy-guidelines` skill（Trae IDE 层面），但 DevFlow 管道内的 coding agent（code_generation、test_generation、code_review）的 prompt 中尚未内化这些原则。

## 现状分析

### 已有机制
1. **Reference Document System** (`devflow/references/`)：通过 front matter 的 `applicable_stages` 字段，在运行时将参考文档注入 agent prompt
2. **Agent System Prompts**：每个 agent 有独立的 system prompt（`prompt.py`），定义角色、工具、输出格式
3. **Trae IDE Skill**：`karpathy-guidelines` skill 已安装，影响 Trae 助手行为

### 缺口
1. DevFlow 管道 agent 的 system prompt 缺少 Karpathy 原则约束
2. 没有面向 coding agent 的 Karpathy 参考文档
3. code_generation agent 容易过度工程、触碰无关代码
4. test_generation agent 缺乏"目标驱动"验证循环
5. code_review agent 缺少对"简洁性"和"精准修改"的评审维度

## 实施方案

### 步骤 1：创建 Karpathy 编码指南参考文档

**文件**：`devflow/references/karpathy-coding-guidelines.md`

- 使用与其他参考文档相同的 front matter 格式
- `applicable_stages: [code_generation, test_generation, code_review]`
- `priority: 15`（高优先级，确保被注入）
- 内容将四个原则转化为 DevFlow agent 可执行的行为规范
- 针对不同 agent 角色给出具体指引

### 步骤 2：增强 Code Generation Agent 的 System Prompt

**文件**：`devflow/code/prompt.py`

在 `CODE_GENERATION_SYSTEM_PROMPT` 中增加 Karpathy 原则约束段落：

- **编码前思考**：要求 agent 在修改文件前先 read_file 了解上下文，遇到歧义时在 warnings 中标注
- **简洁优先**：只实现方案中明确要求的变更，不添加"灵活性"或"可配置性"，不创建未要求的抽象
- **精准修改**：使用 edit_file 而非 write_file 修改已有文件，不"改进"相邻代码，匹配现有风格
- **目标驱动**：每轮 tool 调用后验证结果，finish 时 summary 必须说明每个 changed_file 对应方案中的哪个变更项

### 步骤 3：增强 Test Generation Agent 的 System Prompt

**文件**：`devflow/test/prompt.py`

在 `TEST_GENERATION_SYSTEM_PROMPT` 中增加 Karpathy 原则约束段落：

- **编码前思考**：先检测已有测试框架和模式，复用而非重造
- **简洁优先**：只测试方案中明确的功能点，不为不可能发生的场景写测试
- **精准修改**：不修改被测代码，不改动已有测试（除非方案要求）
- **目标驱动**：生成测试后必须执行验证，记录 pass/fail 结果作为成功标准

### 步骤 4：增强 Code Review Agent 的 System Prompt

**文件**：`devflow/review/prompt.py`

在 `CODE_REVIEW_SYSTEM_PROMPT` 的"重点检查"中增加 Karpathy 维度：

- **简洁性审查**：变更是否过度复杂？200 行能搞定的是否写成了 1000 行？是否存在未要求的抽象？
- **精准性审查**：diff 中是否有与方案无关的改动？是否"改进"了不应触碰的代码？
- **假设审查**：代码中是否有隐含假设未在方案中声明？是否有硬编码的魔法值？
- 将这些作为新的 `category` 选项：`simplicity`、`precision`

### 步骤 5：增强 Solution Design Agent 的 System Prompt

**文件**：`devflow/solution/prompt.py`

在 `SOLUTION_DESIGN_ARCHITECT_PROMPT` 中增加 Karpathy 原则：

- **编码前思考**：方案中必须明确列出假设和权衡，不能默默选择
- **简洁优先**：change_plan 应该是最小变更集，不添加"未来可能需要"的功能
- **目标驱动**：每个 change_plan 条目必须有可验证的完成标准

### 步骤 6：更新 AGENTS.md

**文件**：`AGENTS.md`

在 Working Rules 中增加 Karpathy 编码原则摘要，确保 Trae IDE 层面的 coding 助手也遵循相同原则。

## 影响范围

| 文件 | 变更类型 | 风险 |
|------|---------|------|
| `devflow/references/karpathy-coding-guidelines.md` | 新建 | 低 — 参考文档是注入式的，不影响已有逻辑 |
| `devflow/code/prompt.py` | 修改 | 低 — 增加 prompt 段落，不改变输出格式 |
| `devflow/test/prompt.py` | 修改 | 低 — 同上 |
| `devflow/review/prompt.py` | 修改 | 低 — 增加 review 维度，扩展 category 枚举 |
| `devflow/solution/prompt.py` | 修改 | 低 — 增加方案设计约束 |
| `AGENTS.md` | 修改 | 低 — 增加工作规则 |

## 验证方式

1. 检查 `ReferenceRegistry` 能否正确加载新参考文档
2. 检查各 agent prompt 增强后是否仍然输出合法 JSON
3. 运行现有测试确保无回归
