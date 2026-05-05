# 功能一 Must-have 缺失项实施日志

日期：2026-05-04

## 调研结果

对照 `docs/功能一.md` 的 Must-have 需求，识别出以下核心差距：

1. **RESTful API 层**（Must-have #4）— 完全缺失
2. **Pipeline 可配置性**（Must-have #1）— 阶段定义硬编码
3. **Pipeline 生命周期管理**（Must-have #1）— 缺少 pause/terminate
4. **运行时 LLM Provider 动态切换**（Must-have #2）— 仅支持静态配置
5. **API 文档**（Must-have #4）— 无 Swagger/OpenAPI

## 实施内容

### 1. RESTful API 层 (`devflow/api.py`)
- 使用 Python 标准库 `http.server` 实现（零依赖，与项目理念一致）
- 端点：
  - `GET /api/v1/pipelines` — 列出 Pipeline 运行（支持 status 筛选和 limit）
  - `POST /api/v1/pipelines` — 创建 Pipeline 运行（支持自定义 stages 和 provider 覆盖）
  - `GET /api/v1/pipelines/{run_id}` — 查询运行状态
  - `DELETE /api/v1/pipelines/{run_id}` — 终止运行
  - `POST /api/v1/pipelines/{run_id}/trigger` — 触发执行
  - `POST /api/v1/pipelines/{run_id}/pause` — 暂停运行
  - `POST /api/v1/pipelines/{run_id}/resume` — 恢复运行
  - `GET /api/v1/pipelines/{run_id}/checkpoint` — 查询检查点
  - `POST /api/v1/pipelines/{run_id}/checkpoint` — 操作检查点（approve/reject）
  - `GET /api/v1/openapi.json` — OpenAPI 3.0.3 规范文档

### 2. Pipeline 可配置性
- `STAGE_NAMES` 拆分为 `DEFAULT_STAGE_NAMES`（常量）和 `STAGE_NAMES`（可变列表）
- `initial_stages()` 支持传入自定义阶段列表
- API 创建 Pipeline 时支持 `stages` 参数自定义阶段

### 3. 生命周期管理
- pause：将运行状态改为 `paused`（仅 running/success 状态可暂停）
- terminate：将运行状态改为 `terminated`（delivered/terminated/failed 不可终止）
- resume：将 paused 状态恢复为 `running`

### 4. 运行时 LLM Provider 动态切换
- `config.py` 的 `load_config()` 支持 `provider_override` 参数
- 支持 `DEVFLOW_PROVIDER_OVERRIDE` 环境变量覆盖
- CLI `devflow start --provider <name>` 参数
- API 创建 Pipeline 时支持 `provider` 字段

### 5. OpenAPI 文档
- 内嵌 OpenAPI 3.0.3 规范，覆盖所有端点
- `GET /api/v1/openapi.json` 端点返回完整规范

### 6. CLI 新增命令
- `devflow serve --host --port --out-dir` — 启动 RESTful API 服务器

## 测试结果

- 新增 20 个 API 测试（`tests/test_api.py`），全部通过
- 全量 127 个测试通过，无回归
