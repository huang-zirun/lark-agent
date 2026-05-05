# Tasks

- [x] Task 1: 扩展后端数据聚合模块 `metrics.py`
  - [x] SubTask 1.1: 实现 `get_active_run(out_dir)` —— 扫描所有 run.json，返回 status 为 running/paused 的最新运行，无则返回 None
  - [x] SubTask 1.2: 实现 `get_run_detail(run_dir)` —— 聚合 run.json、各阶段 artifact 摘要、checkpoint 记录、LLM 调用记录、Token 汇总、交付信息
  - [x] SubTask 1.3: 实现 `get_run_llm_trace(run_dir)` —— 扫描 `*-llm-request.json` 和 `*-llm-response.json`，提取 system_prompt/user_prompt 摘要、content 摘要、usage、duration_ms，按阶段分组
  - [x] SubTask 1.4: 实现 `get_run_artifacts(run_dir)` —— 读取各阶段 artifact JSON（requirement.json、solution.json、code-generation.json、test-generation.json、code-review.json、delivery.json），提取结构化摘要
  - [x] SubTask 1.5: 实现 `get_run_diff(run_dir, stage)` —— 读取指定阶段的 diff 文件（code-generation.diff / test-generation.diff / delivery.diff），返回文本内容

- [x] Task 2: 扩展 REST API 层 `api.py`
  - [x] SubTask 2.1: 在 `_ROUTE_PATTERNS` 中注册 5 个新路由
  - [x] SubTask 2.2: 在 `OPENAPI_SPEC` 中新增端点定义
  - [x] SubTask 2.3: 实现 `_handle_metrics_active_run()` 处理函数
  - [x] SubTask 2.4: 实现 `_handle_metrics_run_detail(run_id)` 处理函数
  - [x] SubTask 2.5: 实现 `_handle_metrics_run_llm_trace(run_id)` 处理函数
  - [x] SubTask 2.6: 实现 `_handle_metrics_run_artifacts(run_id)` 处理函数
  - [x] SubTask 2.7: 实现 `_handle_metrics_run_diff(run_id)` 处理函数，支持 `type` 查询参数

- [x] Task 3: 重构前端页面布局与组件
  - [x] SubTask 3.1: 创建 `src/hooks/useRunDetail.ts` —— 封装 useActiveRun、useRunDetail、useRunLlmTrace、useRunArtifacts、useRunDiff 数据获取 hooks，含智能轮询（running 时 3 秒，否则 10 秒）
  - [x] SubTask 3.2: 创建 `src/components/Sidebar.tsx` —— 左侧运行列表侧边栏，展示最近运行，支持点击切换，活跃运行高亮
  - [x] SubTask 3.3: 创建 `src/components/PipelineStepper.tsx` —— 水平 Pipeline 阶段 Stepper，展示 6 阶段状态，支持点击定位
  - [x] SubTask 3.4: 创建 `src/components/StageDetailPanel.tsx` —— 阶段详情面板，展示状态、耗时、Token、产物卡片、审批记录、Diff 预览
  - [x] SubTask 3.5: 创建 `src/components/ArtifactCard.tsx` —— 产物摘要卡片，根据阶段类型展示不同字段
  - [x] SubTask 3.6: 创建 `src/components/ApprovalCard.tsx` —— 审批记录卡片，展示审批状态、决策人、时间、理由
  - [x] SubTask 3.7: 创建 `src/components/LlmTracePanel.tsx` —— 右侧 LLM 推理详情面板，展示 System/User Prompt 摘要、模型输出、Token 统计
  - [x] SubTask 3.8: 创建 `src/components/DiffViewer.tsx` —— Diff 预览组件，语法高亮显示变更内容，默认折叠
  - [x] SubTask 3.9: 创建 `src/components/EmptyState.tsx` —— 无运行数据时的引导空状态
  - [x] SubTask 3.10: 重写 `src/App.tsx` —— 三栏布局（侧边栏 + 中央区 + 右侧栏），组合所有新组件

- [x] Task 4: 清理旧组件与依赖
  - [x] SubTask 4.1: 删除 `StageStatsChart.tsx`、`RunsTrendChart.tsx`、`TokenUsageChart.tsx`、`KpiCards.tsx`、`RunDetailDialog.tsx`
  - [x] SubTask 4.2: 删除 `src/hooks/useMetrics.ts` 中不再使用的 hooks（useOverview、useStageStats、useTokenUsage），保留 useRecentRuns 并重构为 useRunList
  - [x] SubTask 4.3: 从 `package.json` 移除 `recharts` 依赖
  - [x] SubTask 4.4: 更新 `Header.tsx` —— 简化为项目标题和刷新按钮

- [x] Task 5: 构建与集成验证
  - [x] SubTask 5.1: 运行 `npm run build` 验证构建成功
  - [x] SubTask 5.2: 启动 Python API 服务器，验证新 API 端点返回正确 JSON 结构
  - [x] SubTask 5.3: 在浏览器中验证三栏布局、Pipeline Stepper、阶段详情、LLM 推理面板、审批卡片、Diff 预览
  - [x] SubTask 5.4: 验证自动刷新和运行切换功能
  - [x] SubTask 5.5: 运行现有 API 测试套件，确保无回归

# Task Dependencies

- Task 2 依赖 Task 1（API 处理函数调用 metrics.py 的新增函数）
- Task 3 可与 Task 1/2 并行开发（使用 mock 数据），但最终集成依赖 Task 2 完成
- Task 4 依赖 Task 3 完成后再清理
- Task 5 依赖 Task 1-4 全部完成
