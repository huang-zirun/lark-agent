# 可运行程序交付最小方案

日期：2026-05-07

## 背景

功能一主体已具备：6 阶段 Pipeline、LangGraph 编排、2 个 Human-in-the-Loop 检查点、REST API、OpenAPI 文档、零构建 Dashboard、LLM Provider 配置、语义索引和本地 artifact 记录。

当前交付重点不是继续扩功能，而是让评委能用最少步骤在本地启动、查看、触发、审批并看到最终产物。

## 成功标准

1. 评委从干净仓库可以按一份文档启动 API 和 Dashboard。
2. `GET /dashboard`、`GET /docs`、`GET /api/v1/openapi.json` 可访问。
3. REST API 可以创建 Pipeline 运行，并通过 trigger/checkpoint 接口驱动到检查点和后续阶段。
4. 明确区分“无密钥可启动展示”和“有 LLM/飞书配置可跑真实端到端”的路径。
5. 提供一键命令或等效脚本，避免要求评委理解内部 CLI 组合。
6. 交付前至少通过 `compileall` 和一组 API/配置/检查点相关单元测试。

## 当前发现

- `uv run devflow --help` 与 `uv run devflow serve --help` 已验证可用。
- `uv run python -m compileall devflow` 已通过。
- 最小测试集 `tests.test_pipeline_config tests.test_checkpoint` 已通过，共 31 个测试。
- `uv run devflow intake doctor --skip-auth` 在空演示配置下会失败，因为仍要求 `lark.test_doc`。README 当前把它放在预检步骤中，会造成交付体验断点。
- 仓库暂无 `Dockerfile`/`docker-compose.yml`，但已有 `uv`、`package.json`、`npm run dev`、`Procfile` 和 `devflow serve/start` 入口。
- API/Dashboard 路径足够支撑功能一展示；飞书 Bot 路径适合加分演示，但不应作为唯一启动路径。

## 最小实现路线

### 路线 A：最快可交付，推荐

不引入 Docker，提供 PowerShell 一键运行脚本和交付文档：

1. 新增 `scripts/devflow-demo.ps1`
   - 设置 `$env:PYTHONUTF8="1"`。
   - 检查 `uv` 是否可用。
   - 如果缺少 `config.json`，从 `config.example.json` 复制。
   - 启动 `uv run devflow serve --host 127.0.0.1 --port 8080`。
   - 打印 Dashboard、Swagger、OpenAPI 地址。

2. 新增 `docs/可运行程序交付指南.md`
   - “只看平台/API/仪表盘”的启动步骤。
   - “跑真实端到端 Pipeline”的配置项：LLM provider/api_key/model、workspace.root/default_repo，飞书配置作为可选。
   - REST 演示命令：创建运行、触发运行、审批检查点、查看产物。
   - 常见错误：缺 LLM、缺 workspace、端口占用、飞书未登录。

3. 修正 README 预检描述
   - 把 `intake doctor` 标注为“飞书真实采集预检”，不要作为基础启动必跑项。
   - 基础可运行验证改为：`uv run devflow --help`、`uv run devflow serve --help`、访问 `/docs`。

4. 可选小修
   - 给 `intake doctor` 增加 `--skip-lark-doc` 或拆出 `devflow doctor`，避免空配置下基础预检失败。

优点：改动小、Windows/uv 项目风格一致、最快形成可运行交付。
缺点：不是 Docker Compose，但属于“等效一键部署方案”。

### 路线 B：补 Docker Compose

新增 `Dockerfile` + `docker-compose.yml`，只运行 API/Dashboard：

- 容器内安装 Python 3.11、uv，复制仓库，执行 `uv run devflow serve --host 0.0.0.0 --port 8080`。
- `config.json` 通过 bind mount 或环境变量提供。
- 飞书 Bot 不放进默认 compose，因为 lark-cli 登录态和本机交互授权会让评委启动复杂化。

优点：更贴近赛题“Docker Compose”表述。
缺点：LLM/飞书密钥、workspace 路径挂载、Windows 路径映射会增加现场故障点。

## 推荐结论

先走路线 A，确保当天能交付、能演示、能解释。Docker Compose 作为补充而不是主路径。

核心交付叙事：

- 默认启动 API + Dashboard，证明平台可运行。
- 用 Swagger/API 创建 Pipeline，证明 API-first。
- 填入 LLM 和 workspace 后触发真实 Pipeline，证明端到端。
- 两次 checkpoint approve/reject 通过 CLI/API 展示，证明 Human-in-the-Loop。
- 最终 artifact 和 diff 在 Dashboard/本地目录展示，证明可交付代码变更。

## 验证命令

```powershell
uv run devflow --help
uv run devflow serve --help
uv run python -m compileall devflow
uv run python -m unittest tests.test_pipeline_config tests.test_checkpoint -v
```
