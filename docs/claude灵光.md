好，我已经完成了大规模调研，现在进行第一性原理的深度分析。让我把所有洞察整合成一份策略图谱。我的调研已经完成。以下是深度分析报告，先呈现整体架构图，再给出完整策略。---

## 深度赛题解析与竞争策略

### 第一性原理：这道题真正在考什么？

赛题本质上是在问一个问题：**能不能把一个"人力流水线"变成"AI流水线"，同时把飞书变成这个流水线的神经系统？** 当前所有 Code Agent（Copilot、Cursor、Claude Code）只解决了流水线的中间一段——"写代码"。赛题想要的是整条链路的闭环。这正是你的差异化机会。

---

### 一、战场扫描：已有项目资产

**你可以直接复用的关键资产（无需重造轮子）：**

1. **`larksuite/cli`（MIT 协议，官方出品）** — 这是你最重要的发现。飞书官方开源了 Lark CLI，覆盖消息、文档、多维表格、电子表格、日历、邮箱、任务、会议等核心业务域，提供 200+ 命令及 22 个 AI Agent Skills，专为 Agent 原生设计，适配主流 AI 工具，Agent 无需额外适配即可操作飞书。这意味着你的 Pipeline Engine 通过 MCP 调用 `larksuite/cli` 就能覆盖大部分飞书集成需求。

2. **`openai/openai-agents-python`（OpenAI 官方 SDK）** — 内置了 Human-in-the-Loop 机制、函数工具的自动 schema 生成、MCP server 工具调用，以及 Sessions 持久内存层。Human-in-the-Loop 和 Pipeline 编排直接用这套来做，省去大量底层工作。

3. **`PydanticAI`** — 支持 Human-in-the-Loop 工具审批，可轻松标记某些工具调用在执行前需要人工确认；支持 Durable Execution（持久执行），让 Agent 能在 API 故障或重启后恢复进度，处理长期异步工作流。这正好对应 Pipeline 的"暂停/恢复"生命周期要求。

4. **`ORCH` 项目（GitHub 37 stars）** — 一个 CLI 编排器，将 Claude Code、Codex 和 Cursor 作为类型化任务队列管理，实现状态机（todo→in_progress→review→done）、自动重试、Agent 间消息传递和 TUI 仪表板。这个状态机设计可以直接借鉴。

5. **`Forge` 项目** — 一个自主的规格驱动开发循环，三命令流水线（头脑风暴规格、规划任务 DAG、自主执行），带有上下文持续、回溯追踪 bug 到规格缺口的功能，以及 Claude-on-Claude 代码评审。"Claude 评审 Claude 写的代码"这个模式完全可以移植到你的评审 Agent。

---

### 二、核心架构设计决策

**技术栈选型（根据赛题约束最优解）：**

| 层次 | 选择 | 理由 |
|------|------|------|
| 后端框架 | FastAPI + Python | 赛题推荐，自动 OpenAPI 文档，async 支持 |
| Agent 框架 | PydanticAI 或 OpenAI Agents SDK | Human-in-the-Loop 原生支持，LLM Provider 可切换 |
| 飞书集成 | `larksuite/cli` via MCP | 官方出品，22个 Agent Skills 开箱即用 |
| 代码 Agent 内循环 | Claude Code SDK / Gemini CLI 非交互模式 | OpenCode 支持非交互模式 `opencode -p "你的 prompt"`，在此模式下处理 prompt 并将结果输出到标准输出后退出，所有权限自动批准 |
| 代码库索引 | ChromaDB + Tree-sitter | 语义搜索 + 语法感知，成本低 |
| 持久化 | SQLite（开发）/ PostgreSQL（生产） | 存 Pipeline 状态、Agent 日志、Token 消耗 |

---

### 三、你的核心差异化：需求分析 Agent 的精准调优

现有 Code Agent 的盲区不在"写代码"，而在**需求的语义理解**。你提到的调优思路是赛题的制胜关键：

**调优路径：**
1. **从飞书云文档拉取 PRD** → 用 `larksuite/cli` 读取文档结构（标题层级、表格、注释）
2. **需求分析 Agent 内循环** — 参考 Gemini CLI 的 `/plan` 命令思路：Agent 先生成一份"需求理解书"，列出歧义点，**主动通过飞书机器人向产品经理提问**，收到回复后更新理解，直到输出结构化需求文档
3. **验收标准自动生成** — 从 PRD 中提取业务规则，自动生成 Given/When/Then 格式的验收标准（这是大多数工具没有的）
4. **GitHub Skills 作为 Prompt 优化素材** — `larksuite/cli` 本身已经经过 Agent 实测验证，其 Skills 的 Prompt 设计方法论可以借鉴到你自己的需求分析 Prompt 中

---

### 四、飞书集成的三个杀手级场景

**场景1：需求注入**（区别于普通 API 触发）
- 产品经理在飞书文档里写完 PRD，@机器人 "启动开发流程"
- Agent 自动读取文档、解析需求、发起 Pipeline
- 整个过程不需要打开任何其他工具

**场景2：智能化审批卡片**（而不是简单的 Approve/Reject 按钮）
- 检查点触发时，机器人发送一张**结构化飞书消息卡片**，展示：当前阶段输出摘要、影响文件列表、风险评估、Diff 预览
- 审批人可以直接在卡片上点 "Approve" / "Reject + 原因"
- Reject 时输入框让审批人填写修改意见，自动携带进下一轮 Agent 执行

**场景3：项目报告回写**
- Pipeline 完成后，自动在对应飞书云文档追加"AI 开发日志"节点
- 多维表格中的任务状态自动从"待开发"更新为"待合并"，并附上 PR 链接

---

### 五、加分项攻略（最高性价比顺序）

**1. 可观测性面板（最直观加分）**
用 FastAPI + Server-Sent Events 推送实时状态，前端一个简单 React 页面展示每个 Stage 的耗时、Token 消耗、Agent 推理过程。这个视觉冲击力极强，评委一眼就能看到你的系统在"工作"。

**2. 自动回归（技术含量最高）**
当评审 Agent 发现问题时，直接触发修复循环：评审报告 → 代码生成 Agent（携带问题列表）→ 重新生成 → 重新评审，最多重试 3 次。参考 agx 项目的 Checkpoint-based 执行引擎，实现持久的 Wake→Work→Sleep 循环，可以保证跨会话恢复。

**3. Pipeline 模板**
预设三种模板（Bug 修复 / 新功能 / 重构），每种模板的 Stage 组合不同，评审 Agent 的 System Prompt 侧重点也不同。这个实现成本低，演示效果好。

---

### 六、端到端演示脚本（必须项）

根据赛题要求，演示用你的平台给自己加功能（eating your own dog food）：

> **输入需求**："给 DevFlow Engine 的 Pipeline 列表页增加按状态筛选功能"
>
> 1. 飞书机器人接收需求 → 需求分析 Agent 输出结构化需求（含验收标准）
> 2. 飞书卡片推送审批 → 产品经理点 Approve
> 3. 方案设计 Agent 扫描代码库，输出影响文件：`pipeline/router.py`、`frontend/PipelineList.jsx`
> 4. 代码生成 Agent 修改两个文件，生成 Diff
> 5. 测试 Agent 生成单测，评审 Agent 给出评审报告
> 6. 飞书卡片推送代码审批 → 开发者点 Approve
> 7. 交付 Agent 创建 Git 分支、提交代码、发起 PR
> 8. 飞书机器人推送完成通知，云文档记录开发日志

**整个流程应该能在 5 分钟内完成演示**，这是你打动评委的核心时刻。

---

### 七、风险与应对

| 风险 | 应对 |
|------|------|
| LLM 输出不稳定，Pipeline 卡死 | 每个 Agent 调用加超时+重试，Stage 失败可手动重跑 |
| 飞书 API 调用限额（免费版 1万次/月） | 演示时用测试账号，关键调用做本地缓存 |
| 代码生成质量不稳定 | 提供 Mock 模式，演示时可切换到预设的高质量输出 |
| 多 LLM Provider 配置复杂 | 用环境变量统一管理，UI 提供切换开关，演示时用两种：Claude + Gemini |

---

**一句话总结策略**：把 `larksuite/cli` 的 22 个 Agent Skills 当作飞书集成的基础设施，把 PydanticAI 的 Human-in-the-Loop 作为检查点引擎，把需求分析 Agent 的深度调优作为差异化亮点，以"飞书全链路闭环"作为最终演示的视觉冲击力。这三件事做扎实，就能在这道题上站到顶层。