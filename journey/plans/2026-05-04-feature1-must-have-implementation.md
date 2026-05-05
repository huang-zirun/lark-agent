# 功能一 Must-have 缺失项调研与实施计划

日期：2026-05-04

## 调研结论

对照 `docs/功能一.md` 的 Must-have 需求，当前代码库的核心差距如下：

### 严重缺失（Must-have 级别）

1. **RESTful API 层**（Must-have #4）— 完全缺失
   - 无 HTTP 服务器、无 REST 端点
   - 缺少 Pipeline CRUD、执行触发、状态查询、检查点操作
   - 缺少 Swagger/OpenAPI 文档

2. **Pipeline 可配置性**（Must-have #1）— 阶段定义硬编码
   - `STAGE_NAMES` 在 `pipeline.py` 中硬编码
   - 不支持用户自定义阶段组合、排序或增删

3. **Pipeline 生命周期管理不完整**（Must-have #1）
   - 启动 ✅、恢复 ✅
   - 暂停 ❌（无 pause 命令/API）
   - 终止 ❌（无 cancel/terminate 命令/API）

### 部分缺失

4. **运行时 LLM Provider 动态切换**（Must-have #2）
   - 支持多 Provider 配置但不支持运行时切换

## 实施计划

### Phase 1: RESTful API 层
- 使用 Python 标准库 `http.server` 实现（零依赖，与项目理念一致）
- 端点设计：
  - `POST /api/v1/pipelines` — 创建 Pipeline 运行
  - `GET /api/v1/pipelines` — 列出 Pipeline 运行
  - `GET /api/v1/pipelines/{run_id}` — 查询单个运行状态
  - `POST /api/v1/pipelines/{run_id}/trigger` — 触发执行
  - `POST /api/v1/pipelines/{run_id}/pause` — 暂停运行
  - `POST /api/v1/pipelines/{run_id}/resume` — 恢复运行
  - `POST /api/v1/pipelines/{run_id}/terminate` — 终止运行
  - `GET /api/v1/pipelines/{run_id}/checkpoint` — 查询检查点
  - `POST /api/v1/pipelines/{run_id}/checkpoint` — 操作检查点（approve/reject）
  - `GET /api/v1/openapi.json` — OpenAPI 规范文档

### Phase 2: Pipeline 可配置性
- 将 `STAGE_NAMES` 提取为可配置项
- 支持通过配置文件定义阶段列表
- 保留默认6阶段作为内置模板

### Phase 3: 生命周期管理
- 在 Pipeline 运行记录中增加 `paused`/`terminated` 状态
- 实现 pause/terminate 逻辑

### Phase 4: 运行时 LLM Provider 切换
- API 端点支持 per-request 指定 provider
- CLI 支持 `--provider` 参数

### Phase 5: OpenAPI 文档
- 自动生成 OpenAPI 3.0 规范
- 提供 Swagger UI 入口
