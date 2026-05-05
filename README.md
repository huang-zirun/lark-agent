# DevFlow Engine

> **AI 驱动的研发全流程引擎** —— 在飞书群里发一条需求消息，自动完成从需求分析到代码交付的完整 Pipeline。

飞书 AI 校园挑战赛 · 飞书 AI 产品创新赛道 · 课题三：基于 AI 驱动的需求交付流程引擎

---

## 一句话讲清楚

**Pipeline 是骨架，Agent 是肌肉，人类做决策。** 用户输入自然语言需求，DevFlow 将其拆解为 6 阶段 AI Agent Pipeline，每个阶段由专门的 Agent 执行，人类在关键检查点做 Approve/Reject 决策，最终产出可交付的代码变更。

## 系统亮点

- **6 阶段 Agent 编排**：需求分析 → 方案设计 → 代码生成 → 测试生成 → 代码评审 → 交付打包，LangGraph 驱动的完整 Pipeline
- **2 处 Human-in-the-Loop 检查点**：方案设计审批 + 代码评审确认，支持 Approve/Reject + 飞书审批集成
- **自动修复循环**：代码评审发现阻塞性问题时，自动注入反馈重试一次代码生成，无需人工介入
- **AST 语义索引**：对代码库进行结构化理解（Python + JS/TS），Agent 写代码前先理解代码库
- **多 Provider 可切换**：支持火山方舟 / 百炼 / DeepSeek / OpenAI / 自定义，运行时动态切换
- **飞书原生集成**：通过 lark-cli WebSocket 长连接监听消息，需求分析后自动创建 PRD 文档和交互卡片
- **Pipeline 可观测性**：实时监控仪表板 + Swagger UI / ReDoc 交互式 API 文档
- **零外部运行时依赖**：Python stdlib + LangGraph，不 vendoring 任何外部 Agent 运行时

## Pipeline 流程

```
用户输入需求（飞书消息 / 文档 / API）
        │
        ▼
┌─────────────────┐
│  需求分析 Agent   │  理解意图，澄清歧义，输出结构化需求
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  方案设计 Agent   │  分析代码库上下文，输出技术方案
└────────┬────────┘
         │
         ▼
    ╔═══════════╗
    ║ 检查点 ①  ║  人工审批方案（飞书审批 / Bot 消息）
    ╚═════╤═════╝
          │ Approve
          ▼
┌─────────────────┐
│  代码生成 Agent   │  按方案逐文件生成/修改代码
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  测试生成 Agent   │  检测测试框架，生成/补充测试并执行
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  代码评审 Agent   │  只读审查 + 一次自动修复机会
└────────┬────────┘
         │
         ▼
    ╔═══════════╗
    ║ 检查点 ②  ║  人工确认代码评审
    ╚═════╤═════╝
          │ Approve
          ▼
┌─────────────────┐
│   交付 Agent     │  打包变更、测试证据、评审结论、合并建议
└─────────────────┘
```

## 技术栈

| 层级 | 技术选型 |
|------|----------|
| Pipeline 编排 | LangGraph（状态图 + 检查点恢复） |
| 后端 | Python 3.11+, stdlib HTTP Server |
| 前端仪表板 | React 18, TypeScript, Vite, Tailwind CSS |
| 飞书集成 | lark-cli 1.0.23（WebSocket 长连接） |
| LLM 接入 | OpenAI-compatible Chat Completions |
| 语义索引 | Python ast 模块 + tree-sitter（JS/TS 可选） |
| 包管理 | uv（Python）, npm（前端 + lark-cli） |

## 项目结构

```
devflow/
├── intake/          # 需求分析 Agent（文档/消息/Bot 事件读取 + LLM/启发式分析）
├── solution/        # 方案设计 Agent（代码库上下文扫描 + 技术方案生成）
├── code/            # 代码生成 Agent（受限文件工具 + workspace 边界检查）
├── test/            # 测试生成 Agent（测试栈检测 + 测试生成/执行）
├── review/          # 代码评审 Agent（只读审查 + 自动修复循环）
├── delivery/        # 交付 Agent（变更打包 + Git 状态 + 合并建议）
├── semantic/        # AST 语义索引（符号提取 / 引用追踪 / 调用链查询）
├── api.py           # RESTful API（10 端点 + OpenAPI 3.0.3）
├── graph_runner.py  # LangGraph 编排器
├── pipeline.py      # Pipeline 生命周期管理
├── checkpoint.py    # 检查点状态机
├── llm.py           # 多 Provider LLM 客户端
├── cli.py           # CLI 入口
└── config.py        # 配置加载
dashboard/           # Pipeline 实时监控仪表板（React SPA）
docs/                # 项目文档
```

## 快速开始

### 1. 安装前置条件

```powershell
# Python 包管理
pip install uv

# 飞书 CLI
npm.cmd install -g @larksuite/cli@1.0.23
npx.cmd skills add larksuite/cli -y -g
lark-cli config init --new
lark-cli auth login --recommend
```

### 2. 配置项目

```powershell
Copy-Item .\config.example.json .\config.json
```

编辑 `config.json`，填写必要字段：

- `llm.api_key`：LLM API Key
- `llm.model`：模型名或推理接入点 ID
- `lark.app_id` / `lark.app_secret`：飞书开放平台凭证

### 3. 预检

```powershell
uv run devflow intake doctor
uv run devflow intake doctor --check-llm
```

### 4. 启动服务

**方式一：飞书 Bot 一键启动（推荐）**

```powershell
uv run devflow start
```

在飞书群里给 Bot 发消息即可触发完整 Pipeline：

```
需求：给 DevFlow 增加方案设计 agent
仓库：D:\lark
```

或新建项目：

```
需求：做一个贪吃蛇小游戏
新建项目：snake-game
```

**方式二：REST API 启动**

```powershell
uv run devflow serve --host 127.0.0.1 --port 8080
```

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/api/v1/pipelines" -ContentType "application/json" -Body '{"requirement_text":"实现一个登录页","provider":"deepseek"}'
```

**方式三：CLI 逐步执行**

```powershell
# 需求分析
uv run devflow intake from-doc --doc "<飞书文档 URL>" --out ".\artifacts\requirements\requirement.json"

# 方案设计
uv run devflow design from-requirement --requirement ".\artifacts\runs\<run_id>\requirement.json" --repo "D:\lark" --out ".\artifacts\runs\<run_id>\solution.json"

# 代码生成（方案审批后）
uv run devflow code generate --solution ".\artifacts\runs\<run_id>\solution.json" --out ".\artifacts\runs\<run_id>\code-generation.json"

# 测试生成
uv run devflow test generate --run "<run_id>"

# 代码评审
uv run devflow review generate --run "<run_id>"

# 交付打包（评审确认后）
uv run devflow delivery generate --run "<run_id>"
```

**方式四：一键启动全部服务**

```powershell
npm run dev
```

同时启动 API 服务、Bot 监听和前端仪表板。

### 5. 访问仪表板和 API 文档

- Pipeline 仪表板：`http://127.0.0.1:5173`
- Swagger UI：`http://127.0.0.1:8080/docs`
- ReDoc：`http://127.0.0.1:8080/redoc`
- OpenAPI JSON：`http://127.0.0.1:8080/api/v1/openapi.json`

## 6 阶段 Agent 详解

### 需求分析 Agent（requirement-intake-agent）

从飞书文档、飞书消息或机器人消息事件读取需求，输出 `devflow.requirement.v1` 结构化 JSON。支持 LLM 分析（默认）和离线启发式分析（`--analyzer heuristic`）双模式。分析成功后自动创建 PRD 飞书文档并回复交互卡片。

### 方案设计 Agent（solution-design-agent）

读取结构化需求和代码库上下文（含 AST 语义索引摘要），输出 `devflow.solution_design.v1` 技术方案 JSON。支持已有仓库（`--repo`）和全新项目（`--new-project`）两种模式。

### 代码生成 Agent（code-generation-agent）

方案审批通过后运行，使用受限文件工具（read/write/edit/glob/grep/semantic_search + 受限 powershell）把方案落实为代码变更。工具循环带 workspace 边界检查和审计日志，输出 `devflow.code_generation.v1` JSON 和 diff。

### 测试生成 Agent（test-generation-agent）

自动检测已有测试框架（Python: pytest/unittest, JS/TS: npm test, Java: Maven/Gradle），优先复用成熟框架生成/补充测试并执行验证。输出 `devflow.test_generation.v1` JSON 和 diff。

### 代码评审 Agent（code-review-agent）

只读审查代码变更、方案和测试结果，区分阻塞问题和非阻塞建议。如果存在阻塞问题，自动注入反馈重试一次代码生成。第二次评审后无论通过与否都进入人工检查点。输出 `devflow.code_review.v1` JSON 和评审文档。

### 交付 Agent（delivery-agent）

代码评审确认后运行，生成 `devflow.delivery.v1` 交付包，汇总变更、测试证据、评审结论、Git 状态和合并建议。不自动提交、推送或创建 PR —— 让人类做最终的 Git 决策。

## Human-in-the-Loop 检查点

### 检查点 ①：方案设计审批

方案设计完成后，Pipeline 暂停等待人工审批。支持两种审批通道：

1. **飞书审批（主通道）**：自动创建第三方审批实例，用户在飞书审批 App 中操作
2. **Bot 消息（回退通道）**：`Approve <run_id>` 通过 / `Reject <run_id>` 驳回

方案质量不达标时，审批会被阻塞（`waiting_approval_with_warnings`），需使用 `Approve <run_id> --force` 强制通过。

### 检查点 ②：代码评审确认

代码评审完成后，Pipeline 暂停等待人工确认。支持同样的两种审批通道。

## 版本化 JSON 契约体系

每个 Agent 的输入输出由版本化 JSON 契约严格定义：

| 契约 | Schema Version | 产出 |
|------|---------------|------|
| 需求分析 | `devflow.requirement.v1` | 结构化需求（含验收标准、质量信号） |
| 方案设计 | `devflow.solution_design.v1` | 技术方案（含变更清单、API 设计） |
| 代码生成 | `devflow.code_generation.v1` | 代码变更集 + diff |
| 测试生成 | `devflow.test_generation.v1` | 测试代码 + 执行结果 + diff |
| 代码评审 | `devflow.code_review.v1` | 评审报告（含问题列表和修复建议） |
| 交付打包 | `devflow.delivery.v1` | 可交付代码变更 + 变更摘要 |
| 检查点 | `devflow.checkpoint.v1` | 审批状态、决策记录 |
| Pipeline 运行 | `devflow.pipeline_run.v1` | 运行状态、阶段产物路径、审计信息 |

字段名保持英文确保下游兼容；字段值统一使用简体中文。

## LLM Provider 配置

内置 5 种 Provider，均使用 OpenAI-compatible Chat Completions 接口：

| Provider | Base URL | 说明 |
|----------|----------|------|
| `ark` | `https://ark.cn-beijing.volces.com/api/v3` | 火山方舟（默认） |
| `bailian` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 阿里百炼 |
| `deepseek` | `https://api.deepseek.com` | DeepSeek |
| `openai` | `https://api.openai.com/v1` | OpenAI |
| `custom` | 自定义 `llm.base_url` | 任意兼容接口 |

运行时动态切换：

```powershell
# CLI 级别
uv run devflow start --provider deepseek --once --timeout 60

# API 级别
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/api/v1/pipelines" -ContentType "application/json" -Body '{"requirement_text":"实现一个登录页","provider":"deepseek"}'
```

## AST 语义索引

`devflow.semantic` 模块提供结构化代码理解能力：

- **Python**：内置 `ast` 模块，零依赖
- **JavaScript/TypeScript**：`tree-sitter`（lazy import，未安装时优雅降级）
- **5 种查询**：符号搜索 / 引用查找 / 调用链追踪 / 继承层次 / 依赖分析
- **增量更新**：SHA256 哈希变更检测，只重新索引修改过的文件
- **存储**：JSON 文件（`{workspace}/.devflow-index/`），适用于 1000 文件以内的工作区

## 本地配置

真实凭证放在本地 `config.json`（已 gitignore），先复制模板：

```powershell
Copy-Item .\config.example.json .\config.json
```

核心配置项：

```json
{
  "llm": {
    "provider": "ark",
    "api_key": "",
    "model": "",
    "temperature": 0.2,
    "max_tokens": 2000
  },
  "lark": {
    "app_id": "",
    "app_secret": "",
    "prd_folder_token": ""
  },
  "workspace": {
    "root": "",
    "default_repo": ""
  },
  "approval": {
    "enabled": false
  },
  "semantic": {
    "enabled": true
  }
}
```

## 验证

```powershell
uv run python -m unittest discover -s tests -v
```

## 文档导航

| 文档 | 说明 |
|------|------|
| [功能一命题](docs/功能一.md) | 比赛命题原文与验收标准 |
| [公开版命题](docs/基于%20AI%20驱动的需求交付流程引擎（公开版）.md) | 完整赛题说明 |
| [设计快照](journey/design.md) | 当前架构决策、技术选型与约束 |
| [个人阶段成果](docs/个人阶段成果小结.md) | 5 个开发周期的过程复盘与沉淀 |
