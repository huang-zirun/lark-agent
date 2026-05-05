# 可观测性面板（Observability Dashboard）Spec

## Why

根据 `docs/功能一.md` 的加分项要求，以及 `.trae/documents/功能一实现复查计划.md` 的评估结论，当前 DevFlow Engine 仅具备 `trace.jsonl` 审计日志，缺乏 Pipeline 运行状态的实时可视化能力。用户无法直观查看每个阶段的耗时、Token 消耗、Agent 推理过程、成功/失败率等关键指标。本 Spec 旨在设计并实现一个综合性的可观测性面板，将分散的运行数据聚合为可交互的 Web 可视化界面。

## What Changes

- **新增 REST API 数据端点**：为仪表板提供聚合后的运行指标、阶段统计、Token 消耗趋势、实时状态流等数据接口。
- **新增 React + Tailwind CSS + shadcn/ui 前端仪表板**：使用 Vite 构建，嵌入在 DevFlow API 服务器中 served。
- **新增数据聚合模块**：从 `artifacts/runs/*/run.json`、`trace.jsonl`、`checkpoint.json`、LLM 审计日志中提取并计算指标。
- **扩展 OpenAPI 规范**：将新端点纳入 `OPENAPI_SPEC`。
- **新增构建管道**：Vite 构建前端静态资源，Python API 服务器 serve `dist/` 目录。

## Impact

- Affected specs: `devflow.pipeline_run.v1` 数据读取、`trace.jsonl` 解析、LLM 审计日志解析
- Affected code: `api.py`（新增路由与端点）、新增 `dashboard/` 前端包（React+Vite+Tailwind+shadcn）、新增 `metrics.py` 聚合模块
- 无 Breaking Changes，现有 API 行为保持不变
- 新增 Node.js 构建依赖（Vite、React、Tailwind、shadcn/ui、Recharts）

## Tech Stack

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| 构建工具 | Vite | 快速 bundling，支持 React + TypeScript |
| 框架 | React 18 + TypeScript | 组件化 UI 开发 |
| 样式 | Tailwind CSS | 原子化 CSS，响应式布局 |
| 组件库 | shadcn/ui | 基于 Radix UI 的无样式 headless 组件，配合 Tailwind |
| 图表 | Recharts | React 生态图表库，绘制折线图/柱状图/面积图 |
| 数据获取 | 原生 fetch + React hooks | 轻量，无需额外 HTTP 客户端库 |
| 路由 | 无（单页应用） | 使用组件状态切换 Overview / Run Detail 视图 |

## ADDED Requirements

### Requirement: 仪表板数据 API

The system SHALL 提供一组 RESTful 端点，供前端仪表板获取聚合数据。

#### Scenario: 获取运行概览统计
- **WHEN** 前端请求 `GET /api/v1/metrics/overview`
- **THEN** 返回包含以下字段的 JSON：
  - `total_runs`（总运行数）
  - `runs_today`（今日运行数）
  - `success_rate`（成功率，百分比）
  - `avg_duration_ms`（平均运行耗时）
  - `active_runs`（当前活跃运行数，status 为 running/paused）
  - `pending_checkpoints`（待人工审批数）

#### Scenario: 获取阶段耗时统计
- **WHEN** 前端请求 `GET /api/v1/metrics/stage-stats`
- **THEN** 返回每个阶段的聚合统计：
  - `stage_name`
  - `total_executions`（执行次数）
  - `avg_duration_ms`（平均耗时）
  - `success_count` / `failure_count`（成功/失败次数）
  - `min_duration_ms` / `max_duration_ms`（最小/最大耗时）

#### Scenario: 获取 Token 消耗趋势
- **WHEN** 前端请求 `GET /api/v1/metrics/token-usage`
- **THEN** 返回按运行或按日聚合的 Token 使用数据：
  - `run_id` 或 `date`
  - `prompt_tokens`
  - `completion_tokens`
  - `total_tokens`
  - `provider`（使用的 LLM Provider）

#### Scenario: 获取最近运行列表（增强版）
- **WHEN** 前端请求 `GET /api/v1/metrics/recent-runs?limit=20`
- **THEN** 返回精简的运行列表，包含：
  - `run_id`, `status`, `started_at`, `ended_at`, `duration_ms`
  - `current_stage`（当前阶段）
  - `checkpoint_status`（检查点状态）
  - `provider_override`（使用的 Provider）

#### Scenario: 获取单个运行的详细时间线
- **WHEN** 前端请求 `GET /api/v1/metrics/runs/{run_id}/timeline`
- **THEN** 返回该运行的完整 trace 时间线：
  - 按时间排序的事件列表，包含 `timestamp`, `stage`, `event_type`, `status`, `duration_ms`, `payload`

### Requirement: React + Tailwind + shadcn/ui 前端仪表板

The system SHALL 提供一个基于 React + Tailwind CSS + shadcn/ui 的 Web 可视化界面，通过 Vite 构建为静态资源，嵌入在 API 服务器中通过 `GET /dashboard` 访问。

#### Scenario: 项目初始化与构建
- **GIVEN** `dashboard/` 目录作为独立前端项目
- **THEN** 使用 Vite + React + TypeScript 模板初始化
- **THEN** 配置 Tailwind CSS（`tailwind.config.js`、`postcss.config.js`）
- **THEN** 初始化 shadcn/ui（Vite 风格，`components.json`，配置 alias `@/components`）
- **THEN** 安装 Recharts 用于图表渲染
- **THEN** 配置 `vite.config.ts` 的 `base` 为 `/dashboard/`、`build.outDir` 为 `../devflow/dashboard/dist`

#### Scenario: 概览页面（Overview）
- **WHEN** 用户打开 `/dashboard`
- **THEN** 显示以下 shadcn/ui 组件构成的界面：
  - **KPI 卡片区**：使用 `Card` + `CardHeader` + `CardContent` 组件展示 4 个关键指标（总运行数、成功率、活跃运行、待审批）
  - **阶段耗时分布图**：使用 Recharts `BarChart` 展示各阶段平均耗时
  - **最近 24 小时运行趋势**：使用 Recharts `AreaChart` 展示运行数量趋势
  - **Token 消耗趋势**：使用 Recharts `LineChart` 展示按 Provider 分色的 Token 消耗
  - **最近运行列表**：使用 shadcn/ui `Table` 组件展示运行明细（含 `Badge` 状态标签、进度指示）

#### Scenario: 运行详情页（Run Detail）
- **WHEN** 用户点击某行运行的 "查看详情"
- **THEN** 使用 shadcn/ui `Dialog` 或独立视图展示：
  - **阶段流程图**：使用自定义 Stepper 组件或 `Badge` 序列可视化各阶段状态（pending/running/success/failed/blocked）
  - **时间线**：使用 `ScrollArea` 包裹的垂直时间线组件展示 trace 事件
  - **检查点状态**：使用 `Alert` 或 `Card` 展示审批状态与决策记录
  - **Token 消耗**：使用 `Progress` 或数值卡片展示该运行的 Token 统计
  - **原始日志**：使用 `Collapsible` 组件折叠展示原始 JSON 审计日志

#### Scenario: 实时刷新
- **WHEN** 仪表板页面保持打开
- **THEN** 每 10 秒自动轮询 `GET /api/v1/metrics/overview` 和 `GET /api/v1/metrics/recent-runs`
- **THEN** 使用 React `useEffect` + `setInterval` 实现，组件卸载时清理定时器

#### Scenario: 响应式布局
- **WHEN** 用户在不同屏幕尺寸下查看仪表板
- **THEN** 使用 Tailwind CSS 网格系统（`grid-cols-1 md:grid-cols-2 lg:grid-cols-4` 等）实现自适应布局
- **THEN** 图表容器使用响应式宽高比，避免溢出

### Requirement: 数据聚合与解析

The system SHALL 从现有审计文件中提取并计算指标，不修改现有数据写入逻辑。

#### Scenario: 解析 run.json
- **GIVEN** `artifacts/runs/*/run.json` 文件集合
- **THEN** 提取 `status`, `stages`, `started_at`, `ended_at`, `provider_override`, `checkpoint_status` 等字段

#### Scenario: 解析 trace.jsonl
- **GIVEN** `artifacts/runs/*/trace.jsonl` 文件
- **THEN** 解析每行 JSON，提取阶段事件、耗时、状态变化

#### Scenario: 解析 LLM 审计日志
- **GIVEN** `artifacts/runs/*/*-llm-response.json` 文件
- **THEN** 提取 `usage.prompt_tokens`, `usage.completion_tokens`, `usage.total_tokens`, `usage_source`

#### Scenario: 计算派生指标
- **GIVEN** 上述原始数据
- **THEN** 计算：
  - 运行总耗时 = `ended_at - started_at`（若未结束则到当前时间）
  - 阶段耗时 = 从 trace 事件中 `stage_start` 到 `stage_end` 的差值
  - 成功率 = `success` + `delivered` 数量 / 总数量
  - Token 总和 = 各 LLM 调用之和

### Requirement: 构建与集成

The system SHALL 将 React 前端构建产物集成到 Python API 服务器中。

#### Scenario: 开发模式
- **WHEN** 开发者运行 `npm run dev`（在 `dashboard/` 目录）
- **THEN** Vite 开发服务器启动，支持 HMR 热更新，代理 API 请求到 `http://localhost:8080`

#### Scenario: 生产构建
- **WHEN** 开发者运行 `npm run build`
- **THEN** Vite 将前端构建为静态 HTML/CSS/JS 文件，输出到 `devflow/dashboard/dist/`
- **THEN** `api.py` 的 `GET /dashboard` 返回 `dist/index.html`
- **THEN** `GET /dashboard/assets/*` 返回 `dist/assets/` 下的静态文件（带正确 MIME 类型）

#### Scenario: CLI 集成
- **WHEN** 用户运行 `devflow serve`
- **THEN** 如果 `devflow/dashboard/dist/index.html` 存在，则同时 serve 仪表板；否则仅启动 API 并提示仪表板未构建

## MODIFIED Requirements

### Requirement: API 路由注册
- `api.py` 中的 `_ROUTE_PATTERNS` 和 `_dispatch` 方法需要新增仪表板相关路由：
  - `GET /api/v1/metrics/overview`
  - `GET /api/v1/metrics/stage-stats`
  - `GET /api/v1/metrics/token-usage`
  - `GET /api/v1/metrics/recent-runs`
  - `GET /api/v1/metrics/runs/{run_id}/timeline`
  - `GET /dashboard`（返回 `dist/index.html`）
  - `GET /dashboard/assets/*`（返回构建后的 JS/CSS 文件）

### Requirement: OpenAPI 规范
- `OPENAPI_SPEC` 中新增 `Metrics` 和 `Dashboard` tag，补充上述新 API 端点的规范定义。

### Requirement: package.json
- 根目录 `package.json` 新增 `dashboard` workspace 或独立 `dashboard/package.json`，包含：
  - `dependencies`: `react`, `react-dom`, `recharts`, `lucide-react`, `class-variance-authority`, `clsx`, `tailwind-merge`, `@radix-ui/*`
  - `devDependencies`: `vite`, `@vitejs/plugin-react`, `typescript`, `tailwindcss`, `postcss`, `autoprefixer`, `@types/react`, `@types/react-dom`

## REMOVED Requirements

无
