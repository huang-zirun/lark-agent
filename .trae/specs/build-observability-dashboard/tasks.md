# Tasks

- [x] Task 1: 创建数据聚合模块 `metrics.py`
  - [x] SubTask 1.1: 实现 `load_all_runs(out_dir)` 函数，扫描 `artifacts/runs/*/run.json` 并返回解析后的运行列表
  - [x] SubTask 1.2: 实现 `compute_overview(runs)` 函数，计算总运行数、今日运行数、成功率、平均耗时、活跃运行数、待审批数
  - [x] SubTask 1.3: 实现 `compute_stage_stats(runs)` 函数，按阶段聚合执行次数、平均耗时、成功/失败次数、最小/最大耗时
  - [x] SubTask 1.4: 实现 `compute_token_usage(out_dir)` 函数，扫描 `*-llm-response.json` 提取 Token 消耗并按运行/Provider 聚合
  - [x] SubTask 1.5: 实现 `get_recent_runs(runs, limit=20)` 函数，返回精简的运行列表（含当前阶段、检查点状态、Provider）
  - [x] SubTask 1.6: 实现 `get_run_timeline(run_dir)` 函数，解析 `trace.jsonl` 返回按时间排序的事件列表

- [x] Task 2: 扩展 REST API 层 `api.py`
  - [x] SubTask 2.1: 在 `OPENAPI_SPEC` 中新增 Metrics 相关端点定义
  - [x] SubTask 2.2: 在 `_ROUTE_PATTERNS` 中注册新路由（5 个 API 端点 + 2 个仪表板静态文件路由）
  - [x] SubTask 2.3: 实现 `_handle_metrics_overview()` 处理函数
  - [x] SubTask 2.4: 实现 `_handle_metrics_stage_stats()` 处理函数
  - [x] SubTask 2.5: 实现 `_handle_metrics_token_usage()` 处理函数
  - [x] SubTask 2.6: 实现 `_handle_metrics_recent_runs()` 处理函数
  - [x] SubTask 2.7: 实现 `_handle_metrics_run_timeline(run_id)` 处理函数
  - [x] SubTask 2.8: 实现 `_handle_dashboard()` 返回 `dist/index.html`
  - [x] SubTask 2.9: 实现 `_handle_dashboard_assets(filepath)` 返回构建后的 JS/CSS 文件（带正确 MIME 类型）

- [x] Task 3: 初始化 React + Vite + Tailwind + shadcn/ui 前端项目
  - [x] SubTask 3.1: 在 `dashboard/` 目录执行 `npm create vite@latest . -- --template react-ts`
  - [x] SubTask 3.2: 安装 Tailwind CSS 并配置 `tailwind.config.js`、`postcss.config.js`
  - [x] SubTask 3.3: 初始化 shadcn/ui（`npx shadcn-ui@latest init`），配置 `components.json` 和路径 alias
  - [x] SubTask 3.4: 安装 Recharts 和 lucide-react
  - [x] SubTask 3.5: 配置 `vite.config.ts`：`base: '/dashboard/'`，`build.outDir` 指向 `../devflow/dashboard/dist`
  - [x] SubTask 3.6: 配置开发服务器代理：API 请求代理到 `http://localhost:8080`

- [x] Task 4: 实现仪表板 React 组件
  - [x] SubTask 4.1: 创建 `src/hooks/useMetrics.ts` —— 封装 `useOverview`、`useStageStats`、`useTokenUsage`、`useRecentRuns`、`useRunTimeline` 等数据获取 hooks，含自动轮询（10 秒）
  - [x] SubTask 4.2: 创建 `src/components/KpiCards.tsx` —— 使用 shadcn/ui `Card` 展示 4 个 KPI 指标
  - [x] SubTask 4.3: 创建 `src/components/StageStatsChart.tsx` —— 使用 Recharts `BarChart` 展示阶段耗时分布
  - [x] SubTask 4.4: 创建 `src/components/RunsTrendChart.tsx` —— 使用 Recharts `AreaChart` 展示最近 24 小时运行趋势
  - [x] SubTask 4.5: 创建 `src/components/TokenUsageChart.tsx` —— 使用 Recharts `LineChart` 展示 Token 消耗趋势（按 Provider 分色）
  - [x] SubTask 4.6: 创建 `src/components/RecentRunsTable.tsx` —— 使用 shadcn/ui `Table` + `Badge` 展示最近运行列表
  - [x] SubTask 4.7: 创建 `src/components/RunDetailDialog.tsx` —— 使用 shadcn/ui `Dialog` + `ScrollArea` + `Collapsible` 展示运行详情（阶段流程、时间线、检查点、Token、原始日志）
  - [x] SubTask 4.8: 创建 `src/App.tsx` —— 组合所有组件，使用 Tailwind CSS 网格布局实现响应式页面

- [x] Task 5: 构建与集成验证
  - [x] SubTask 5.1: 运行 `npm run build` 验证构建成功，产物输出到 `devflow/dashboard/dist/`
  - [x] SubTask 5.2: 启动 Python API 服务器，验证 `GET /dashboard` 返回 HTML，`GET /dashboard/assets/*` 返回静态文件
  - [x] SubTask 5.3: 验证所有 Metrics API 端点返回正确 JSON 结构
  - [x] SubTask 5.4: 在浏览器中打开 `/dashboard`，验证页面渲染、图表显示、数据刷新、详情弹窗
  - [x] SubTask 5.5: 运行现有 API 测试套件，确保无回归

# Task Dependencies

- Task 2 依赖 Task 1（API 处理函数调用 metrics.py 的聚合函数）
- Task 3 可独立并行执行（前端项目初始化）
- Task 4 依赖 Task 3（需要项目初始化完成后才能开发组件）
- Task 5 依赖 Task 1、Task 2、Task 4 全部完成
