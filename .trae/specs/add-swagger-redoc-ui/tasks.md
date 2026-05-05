# Tasks

- [x] Task 1: 添加 HTML 模板常量和响应方法
  - [x] SubTask 1.1: 在 `devflow/api.py` 中 `OPENAPI_SPEC` 后定义 `SWAGGER_UI_HTML` 常量（CDN 版本 Swagger UI 5.20.1，指向 `/api/v1/openapi.json`，StandaloneLayout，docExpansion=list，filter=true，tryItOutEnabled=true）
  - [x] SubTask 1.2: 在 `devflow/api.py` 中定义 `REDOC_HTML` 常量（CDN 版本 ReDoc latest，指向 `/api/v1/openapi.json`，hideDownloadButton=false，expandResponses="200,201"）
  - [x] SubTask 1.3: 在 `DevFlowApiHandler` 类中添加 `_html_response(self, html: str)` 方法，设置 Content-Type 为 `text/html; charset=utf-8`

- [x] Task 2: 注册路由和分发逻辑
  - [x] SubTask 2.1: 在 `_ROUTE_PATTERNS` 列表末尾添加 `("GET", r"^/docs$")` 和 `("GET", r"^/redoc$")`
  - [x] SubTask 2.2: 在 `_dispatch` 方法中添加 `/docs` 路由分发（调用 `_html_response(SWAGGER_UI_HTML)`）
  - [x] SubTask 2.3: 在 `_dispatch` 方法中添加 `/redoc` 路由分发（调用 `_html_response(REDOC_HTML)`）

- [x] Task 3: 更新 OpenAPI 规范自描述
  - [x] SubTask 3.1: 在 `OPENAPI_SPEC["paths"]` 中添加 `/docs` GET 操作声明（tag: Meta）
  - [x] SubTask 3.2: 在 `OPENAPI_SPEC["paths"]` 中添加 `/redoc` GET 操作声明（tag: Meta）

- [x] Task 4: 更新启动提示
  - [x] SubTask 4.1: 在 `run_server` 函数中添加 Swagger UI 和 ReDoc URL 的打印输出

- [x] Task 5: 验证
  - [x] SubTask 5.1: 启动服务器，验证 `GET /docs` 返回 Swagger UI 页面
  - [x] SubTask 5.2: 验证 `GET /redoc` 返回 ReDoc 页面
  - [x] SubTask 5.3: 验证 `GET /api/v1/openapi.json` 中包含 `/docs` 和 `/redoc` 声明

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 is independent of Task 1 and Task 2
- Task 4 is independent of Task 1, Task 2, Task 3
- Task 5 depends on Task 1, Task 2, Task 3, Task 4
