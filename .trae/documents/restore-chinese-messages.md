# 计划：将因 Windows GBK 编码问题而英文化的消息恢复为中文

## 背景

项目之前因 Windows 控制台默认使用 GBK (CP936) 编码，导致 Python `print()` 输出中文时出现乱码。为规避此问题，部分控制台输出消息被刻意改为英文。现已通过 `cross-env PYTHONUTF8=1`（package.json）和 PowerShell Profile 永久修复了编码问题，可以将这些英文消息恢复为中文。

## 修改范围

### 1. `devflow/pipeline.py` — `_print_no_default_chat_guidance()` 函数

**行 2063-2078**：Bot 启动引导消息，当前为英文，应改为中文。

| 行号 | 当前英文 | 改为中文 |
|------|---------|---------|
| 2067 | `"  DevFlow Bot Ready"` | `"  DevFlow 机器人已就绪"` |
| 2069 | `"  Users can send messages to the bot in Feishu/Lark"` | `"  用户可以在飞书中向机器人发送消息"` |
| 2070 | `"  to start the development pipeline."` | `"  启动开发流水线。"` |
| 2072 | `"  To enable welcome message on startup, set in config:"` | `"  如需启动时发送欢迎消息，请在配置中设置："` |

### 2. `devflow/cli.py` — 审批默认阻止原因

**行 309**：与 `checkpoint.py:276` 和 `pipeline.py:1261` 中的中文原文形成直接对照。

| 行号 | 当前英文 | 改为中文 |
|------|---------|---------|
| 309 | `"Solution not ready, cannot approve. Use --force to override"` | `"方案未就绪，无法批准。如需强制通过请使用 --force"` |

### 3. `devflow/cli.py` — 审批轮询输出

| 行号 | 当前英文 | 改为中文 |
|------|---------|---------|
| 386 | `f"Poll failed {instance_code}: {exc}"` | `f"轮询失败 {instance_code}：{exc}"` |
| 416 | `f"Updated {checkpoint['run_id']}: {checkpoint['status']}"` | `f"已更新 {checkpoint['run_id']}：{checkpoint['status']}"` |
| 419 | `"No checkpoint updates needed."` | `"无需更新检查点。"` |

### 4. `devflow/cli.py` — `devflow doctor` 状态检查输出

| 行号 | 当前英文 | 改为中文 |
|------|---------|---------|
| 603 | `"Config: OK"` | `"配置：正常"` |
| 604 | `f"LLM provider: {config.llm.provider}"` | `f"LLM 提供者：{config.llm.provider}"` |
| 605 | `f"LLM model: {config.llm.model}"` | `f"LLM 模型：{config.llm.model}"` |
| 606 | `f"LLM base url host: {base_url_host(config.llm)}"` | `f"LLM 基础 URL 主机：{base_url_host(config.llm)}"` |
| 607 | `f"lark-cli executable: {executable}"` | `f"lark-cli 可执行文件：{executable}"` |
| 608 | `f"lark-cli version: {version}"` | `f"lark-cli 版本：{version}"` |
| 611 | `"lark-cli auth: Skipped"` | `"lark-cli 认证：已跳过"` |
| 614 | `"lark-cli auth: OK"` | `"lark-cli 认证：正常"` |
| 617 | `"LLM connectivity: OK"` | `"LLM 连通性：正常"` |

### 5. `devflow/cli.py` — 语义索引构建输出

| 行号 | 当前英文 | 改为中文 |
|------|---------|---------|
| 626 | `"Semantic index built"` | `"语义索引已构建"` |
| 627 | `f"  Build type: {summary.build_type}"` | `f"  构建类型：{summary.build_type}"` |
| 628 | `f"  Total symbols: {summary.total_symbols}"` | `f"  符号总数：{summary.total_symbols}"` |
| 629 | `f"  Total relations: {summary.total_relations}"` | `f"  关系总数：{summary.total_relations}"` |
| 630 | `f"  Total files: {summary.total_files}"` | `f"  文件总数：{summary.total_files}"` |
| 631 | `f"  Language distribution: {lang_dist}"` | `f"  语言分布：{lang_dist}"` |
| 632 | `f"  Time: {summary.build_time_ms}ms"` | `f"  耗时：{summary.build_time_ms}ms"` |

### 6. `devflow/cli.py` — 主入口错误输出

| 行号 | 当前英文 | 改为中文 |
|------|---------|---------|
| 659 | `f"devflow: {exc}"` | `f"devflow 错误：{exc}"` |

### 7. `devflow/api.py` — API 服务器启动信息

| 行号 | 当前英文 | 改为中文 |
|------|---------|---------|
| 867 | `f"DevFlow API Server: http://{host}:{port}"` | `f"DevFlow API 服务器：http://{host}:{port}"` |
| 868 | `f"Swagger UI: http://{host}:{port}/docs"` | `f"Swagger UI：http://{host}:{port}/docs"` |
| 869 | `f"ReDoc: http://{host}:{port}/redoc"` | `f"ReDoc：http://{host}:{port}/redoc"` |
| 870 | `f"Dashboard: http://{host}:{port}/dashboard"` | `f"控制台：http://{host}:{port}/dashboard"` |
| 871 | `f"OpenAPI JSON: http://{host}:{port}/api/v1/openapi.json"` | `f"OpenAPI JSON：http://{host}:{port}/api/v1/openapi.json"` |

### 8. `devflow/graph_runner.py` — LangGraph 入口缺失异常

| 行号 | 当前英文 | 改为中文 |
|------|---------|---------|
| 35 | `"LangGraph entrypoint is missing."` | `"LangGraph 入口点缺失。"` |

### 9. `devflow/semantic/parsers/__init__.py` — 解析超时

| 行号 | 当前英文 | 改为中文 |
|------|---------|---------|
| 70 | `"parse timeout"` | `"解析超时"` |
| 82 | `"parse timeout"` | `"解析超时"` |
| 83 | `"parse timeout"` | `"解析超时"` |

## 不修改的内容

- `raise` 中的中文异常消息 — 已经是中文，无需修改
- `build_welcome_text()` — 已经是中文，无需修改
- `pipeline.py:2176` 的 `f"{result.run_id} {result.status} {result.run_dir}"` — 纯数据输出，status 是英文枚举值，属于数据驱动，不算刻意英文化

## 执行步骤

1. 修改 `devflow/pipeline.py` — `_print_no_default_chat_guidance()` 4 行
2. 修改 `devflow/cli.py` — 审批默认原因 1 行 + 轮询输出 3 行 + doctor 输出 9 行 + 语义索引 7 行 + 主入口 1 行 = 21 行
3. 修改 `devflow/api.py` — 服务器启动信息 5 行
4. 修改 `devflow/graph_runner.py` — 异常消息 1 行
5. 修改 `devflow/semantic/parsers/__init__.py` — 超时消息 3 行
6. 运行 lint/typecheck 验证
