# Swagger UI / ReDoc 交互式 API 文档 Spec

## Why

项目已有 21 个 RESTful API 端点和内嵌的 OpenAPI 3.0.3 JSON 规范（`/api/v1/openapi.json`），但缺少交互式文档界面。用户只能通过原始 JSON 查看规范，无法在线浏览、搜索或直接在浏览器中试调用 API。添加 Swagger UI 和 ReDoc 是 API-First 架构的标配，也是功能一需求中"API 设计规范、文档完整"的明确要求。

## What Changes

- 在 `devflow/api.py` 中新增 `/docs`（Swagger UI）和 `/redoc`（ReDoc）两个 HTML 页面路由
- 新增 `_html_response` 辅助方法，用于返回 HTML 内容
- 新增 `SWAGGER_UI_HTML` 和 `REDOC_HTML` 模块级常量，使用 CDN 加载前端资源
- 在 `_ROUTE_PATTERNS` 中注册新路由
- 在 `_dispatch` 中添加路由分发逻辑
- 在 `OPENAPI_SPEC` 的 `paths` 中声明 `/docs` 和 `/redoc` 端点（自描述）
- 在 `run_server` 启动提示中增加文档 URL

## Impact

- Affected code: `devflow/api.py`（唯一修改文件）
- 无破坏性变更，所有现有端点行为不变
- 新增两个 GET 端点：`/docs`、`/redoc`

## 技术方案选型

**CDN + HTML 字符串常量方案**（推荐，已确认最佳实践）

| 维度 | CDN 方案 | 本地静态文件方案 |
|------|---------|----------------|
| 实现复杂度 | 极低，只需返回一段 HTML | 需下载约 5-10MB 前端资源，需实现静态文件服务 |
| Python 依赖 | 零 | 零 |
| 离线可用性 | 需联网 | 完全离线 |
| 版本锁定 | URL 中指定版本号 | 天然锁定 |
| 与项目理念契合度 | 高 — 项目坚持 stdlib only | 中 — 需额外管理资源目录 |

CDN 版本锁定：Swagger UI `@5.20.1`，ReDoc `latest`（Redoc.ly 官方推荐用法）。

## ADDED Requirements

### Requirement: Swagger UI 交互式文档

系统 SHALL 在 `/docs` 端点提供 Swagger UI 交互式 API 文档页面。

#### Scenario: 用户访问 Swagger UI
- **WHEN** 用户通过浏览器访问 `GET /docs`
- **THEN** 返回 HTTP 200，Content-Type 为 `text/html; charset=utf-8`
- **AND** 页面加载 Swagger UI 前端资源并自动读取 `/api/v1/openapi.json` 规范
- **AND** 用户可浏览所有 API 端点、查看参数/响应模型、在线试调用

#### Scenario: Swagger UI 配置
- **GIVEN** Swagger UI 页面已加载
- **THEN** 使用 StandaloneLayout 布局
- **AND** `docExpansion` 为 `"list"`（默认展开端点列表）
- **AND** `filter` 为 `true`（启用搜索过滤）
- **AND** `tryItOutEnabled` 为 `true`（默认启用 Try it out）

### Requirement: ReDoc 交互式文档

系统 SHALL 在 `/redoc` 端点提供 ReDoc 交互式 API 文档页面。

#### Scenario: 用户访问 ReDoc
- **WHEN** 用户通过浏览器访问 `GET /redoc`
- **THEN** 返回 HTTP 200，Content-Type 为 `text/html; charset=utf-8`
- **AND** 页面加载 ReDoc 前端资源并自动读取 `/api/v1/openapi.json` 规范
- **AND** 用户可浏览三栏式 API 文档（导航、文档、代码示例）

#### Scenario: ReDoc 配置
- **GIVEN** ReDoc 页面已加载
- **THEN** `hideDownloadButton` 为 `false`（显示下载按钮）
- **AND** `expandResponses` 为 `"200,201"`（默认展开成功响应）

### Requirement: OpenAPI 规范自描述

系统 SHALL 在 OpenAPI 规范中声明 `/docs` 和 `/redoc` 端点，使规范自描述。

#### Scenario: 规范中包含文档端点
- **WHEN** 请求 `GET /api/v1/openapi.json`
- **THEN** 返回的 JSON 中 `paths` 包含 `/docs` 和 `/redoc` 的 GET 操作声明
- **AND** 两者均标记为 `Meta` tag

### Requirement: 启动提示包含文档 URL

系统 SHALL 在服务器启动时打印文档 URL。

#### Scenario: 服务器启动输出
- **WHEN** `run_server` 启动
- **THEN** 控制台输出包含 Swagger UI URL（`/docs`）和 ReDoc URL（`/redoc`）
