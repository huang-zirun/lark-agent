# Checklist

## 数据聚合模块

- [x] `metrics.py` 文件存在且可被 `api.py` 导入
- [x] `load_all_runs(out_dir)` 正确扫描并解析所有 `run.json`
- [x] `compute_overview(runs)` 返回的 KPI 数据准确（总运行数、今日运行数、成功率、平均耗时、活跃运行、待审批）
- [x] `compute_stage_stats(runs)` 正确按阶段聚合耗时和成功/失败统计
- [x] `compute_token_usage(out_dir)` 正确从 LLM 审计日志提取 Token 消耗
- [x] `get_recent_runs(runs, limit)` 返回精简列表且包含当前阶段、检查点状态、Provider
- [x] `get_run_timeline(run_dir)` 正确解析 `trace.jsonl` 并按时间排序

## REST API 扩展

- [x] `GET /api/v1/metrics/overview` 返回正确 JSON 结构
- [x] `GET /api/v1/metrics/stage-stats` 返回正确 JSON 结构
- [x] `GET /api/v1/metrics/token-usage` 返回正确 JSON 结构
- [x] `GET /api/v1/metrics/recent-runs` 支持 `limit` 参数并返回正确结构
- [x] `GET /api/v1/metrics/runs/{run_id}/timeline` 对存在的 run_id 返回时间线，对不存在的返回 404
- [x] `GET /dashboard` 返回构建后的 `index.html`（Content-Type: text/html）
- [x] `GET /dashboard/assets/*` 正确返回 JS/CSS 文件（带正确 MIME 类型）
- [x] OpenAPI 规范中新增端点定义完整

## 前端项目初始化

- [x] `dashboard/package.json` 存在且包含 React、Vite、Tailwind、shadcn/ui、Recharts 依赖
- [x] `dashboard/vite.config.ts` 配置正确：`base: '/dashboard/'`，`build.outDir` 指向 `../devflow/dashboard/dist`
- [x] `dashboard/tailwind.config.js` 和 `postcss.config.js` 配置正确
- [x] `dashboard/components.json` 存在且 shadcn/ui 路径 alias 配置正确
- [x] 开发服务器代理配置：API 请求代理到 `http://localhost:8080`
- [x] `npm run build` 成功生成 `devflow/dashboard/dist/index.html` 和 `assets/` 目录

## React 组件实现

- [x] `src/hooks/useMetrics.ts` 存在，包含所有数据获取 hooks 和 10 秒自动轮询
- [x] `src/components/KpiCards.tsx` 使用 shadcn/ui `Card` 正确渲染 4 个 KPI
- [x] `src/components/StageStatsChart.tsx` 使用 Recharts `BarChart` 正确渲染阶段耗时
- [x] `src/components/RunsTrendChart.tsx` 使用 Recharts `AreaChart` 正确渲染 24 小时趋势
- [x] `src/components/TokenUsageChart.tsx` 使用 Recharts `LineChart` 按 Provider 分色渲染 Token 趋势
- [x] `src/components/RecentRunsTable.tsx` 使用 shadcn/ui `Table` + `Badge` 正确渲染运行列表
- [x] `src/components/RunDetailDialog.tsx` 使用 shadcn/ui `Dialog` 正确展示运行详情（阶段流程、时间线、检查点、Token、原始日志）
- [x] `src/App.tsx` 组合所有组件，Tailwind CSS 响应式布局正确

## 集成与回归

- [x] 现有 API 端点（Pipeline CRUD、Checkpoint、OpenAPI）行为无变化
- [x] 现有测试套件全部通过
- [x] 仪表板在无运行数据时显示友好空状态
- [x] 仪表板在有运行数据时所有图表和数据正确展示
- [x] 运行详情弹窗点击后正确显示时间线和阶段状态
- [x] 前端自动轮询每 10 秒刷新数据
