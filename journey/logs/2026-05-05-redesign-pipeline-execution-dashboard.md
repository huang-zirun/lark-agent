# Pipeline 执行监控面板重构日志

## 日期
2026-05-05

## 操作摘要

参考 Trae SOLO 的 Responsive Review / Responsive Context / Plan before Execute 理念，将 DevFlow 仪表板从"事后聚合统计"重构为"Pipeline 执行实时监控"。

## 核心变更

### 后端（Python）

**devflow/metrics.py** 新增 5 个数据聚合函数：
- `get_active_run(out_dir)` — 扫描所有 run.json，返回最新活跃运行
- `get_run_detail(run_dir)` — 聚合 run.json、artifacts、checkpoints、llm_calls、token_summary、delivery
- `get_run_llm_trace(run_dir)` — 解析 llm-request.json 和 llm-response.json，提取 prompt 摘要和模型输出
- `get_run_artifacts(run_dir)` — 提取各阶段产物的结构化摘要
- `get_run_diff(run_dir, stage)` — 读取 diff 文件内容

**devflow/api.py** 新增 5 个 REST API 端点：
- `GET /api/v1/metrics/active-run` — 获取活跃运行
- `GET /api/v1/metrics/runs/{run_id}/detail` — 获取运行完整详情
- `GET /api/v1/metrics/runs/{run_id}/llm-trace` — 获取 LLM 推理链
- `GET /api/v1/metrics/runs/{run_id}/artifacts` — 获取产物摘要
- `GET /api/v1/metrics/runs/{run_id}/diff?type={stage}` — 获取 Diff 内容

### 前端（React + TypeScript）

**新布局**：三栏布局
- 左侧栏（240px）：运行列表 Sidebar
- 中央区：Pipeline Stepper + StageDetailPanel
- 右侧栏（360px）：LlmTracePanel

**新增组件**（8 个）：
- `Sidebar.tsx` — 运行列表，支持点击切换，活跃运行高亮
- `PipelineStepper.tsx` — 6 阶段水平 Stepper，状态指示（pending/running/success/failed/blocked）
- `StageDetailPanel.tsx` — 阶段详情面板，展示状态、耗时、Token、产物、审批、Diff
- `ArtifactCard.tsx` — 产物摘要卡片（6 阶段不同字段）
- `ApprovalCard.tsx` — 审批记录卡片（状态、决策人、时间、理由）
- `LlmTracePanel.tsx` — LLM 推理详情（System/User Prompt、模型输出、Token 统计）
- `DiffViewer.tsx` — Diff 预览组件，语法高亮，默认折叠
- `EmptyState.tsx` — 无运行数据引导空状态

**新增 Hooks**：
- `useRunDetail.ts` — useActiveRun、useRunList、useRunDetail、useRunLlmTrace、useRunDiff
- 智能轮询：running 状态 3 秒，其他 10 秒

**重写组件**：
- `App.tsx` — 三栏布局，自动聚焦活跃运行
- `Header.tsx` — 简化为项目标题 + 刷新按钮

**移除组件**（5 个）：
- StageStatsChart.tsx
- RunsTrendChart.tsx
- TokenUsageChart.tsx
- KpiCards.tsx
- RunDetailDialog.tsx

**移除依赖**：recharts

## 展示内容覆盖

1. ✅ 当前阶段 — Pipeline Stepper 实时状态指示
2. ✅ 当前阶段进度 — Stepper + 阶段详情面板
3. ✅ 消耗时间 — 实时更新的 duration_ms
4. ✅ Token 消耗 — 各阶段 prompt/completion/total tokens
5. ✅ 产物 — 各阶段 artifact 结构化摘要卡片
6. ✅ LLM reasoning 中间过程 — System/User Prompt + 模型输出
7. ✅ 中间文档 — solution.md、code-review.md 等
8. ✅ 审批操作 — checkpoint 审批时间线
9. ✅ 交付成果 — delivery.json + delivery.diff

## 验证结果

- ✅ `npm run build` 构建成功
- ✅ Python 后端导入测试通过
- ✅ API 端点注册验证通过（11 个 paths）
- ✅ 现有测试套件通过（test_api.py、test_checkpoint.py、test_graph_runner.py：47 passed）

## 相关文件

- Spec: `.trae/specs/redesign-pipeline-execution-dashboard/spec.md`
- Tasks: `.trae/specs/redesign-pipeline-execution-dashboard/tasks.md`
- Checklist: `.trae/specs/redesign-pipeline-execution-dashboard/checklist.md`
