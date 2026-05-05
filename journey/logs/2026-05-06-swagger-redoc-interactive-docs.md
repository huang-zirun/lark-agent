# 2026-05-06 Swagger UI / ReDoc 交互式 API 文档

## 背景

项目已有 21 个 RESTful API 端点和内嵌的 OpenAPI 3.0.3 JSON 规范（`/api/v1/openapi.json`），但缺少交互式文档界面。功能一需求中明确要求"API 设计规范、文档完整"。

## 调研结论

对比了 CDN 方案和本地静态文件方案：

| 维度 | CDN 方案 | 本地静态文件方案 |
|------|---------|----------------|
| 实现复杂度 | 极低 | 需管理约 5-10MB 前端资源 |
| Python 依赖 | 零 | 零 |
| 离线可用性 | 需联网 | 完全离线 |
| 与项目理念契合度 | 高（stdlib only） | 中 |

**选择 CDN + HTML 字符串常量方案**，理由：零 Python 依赖，与项目 stdlib-only 理念完全契合，实现成本最低。

也调研了 Python 包（`swagger-ui-bundle`、`apispec` 等），结论是没有适合 stdlib http.server 的轻量级包，现有包要么绑定框架（FastAPI/Flask），要么只是打包了前端资源。

## 实现内容

修改文件：`devflow/api.py`（唯一修改文件）

1. 新增 `SWAGGER_UI_HTML` 常量 — CDN 加载 swagger-ui-dist@5.20.1，StandaloneLayout，docExpansion=list，filter=true，tryItOutEnabled=true
2. 新增 `REDOC_HTML` 常量 — CDN 加载 redoc.standalone.js，hideDownloadButton=false，expandResponses="200,201"，蓝色主题
3. 新增 `_html_response()` 方法 — Content-Type: text/html; charset=utf-8
4. 新增路由 `GET /docs` → Swagger UI，`GET /redoc` → ReDoc
5. OpenAPI spec paths 中自描述 `/docs` 和 `/redoc`（tag: Meta）
6. `run_server` 启动提示增加 Swagger UI、ReDoc URL

## 端点设计

| 端点 | 用途 |
|------|------|
| `GET /docs` | Swagger UI 交互式文档（浏览 + Try it out） |
| `GET /redoc` | ReDoc 三栏式文档（阅读友好） |
| `GET /api/v1/openapi.json` | OpenAPI 3.0.3 JSON 规范（已有） |

## 验证结果

端到端 HTTP 测试全部通过：
- `GET /docs` → 200, text/html, 包含 swagger-ui
- `GET /redoc` → 200, text/html, 包含 redoc
- OpenAPI JSON 中包含 `/docs` 和 `/redoc` 声明
- 现有 21 个端点无回归

## 后续可选

- 离线降级：将 CDN 资源下载到 `devflow/static/` 目录，HTML 中替换为本地路径
