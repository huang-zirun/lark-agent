# Checklist

## 后端数据聚合模块

- [x] `metrics.py` 新增 `get_active_run(out_dir)` 正确返回活跃运行或 None
- [x] `metrics.py` 新增 `get_run_detail(run_dir)` 返回完整的运行详情（run、stages、artifacts、checkpoints、llm_calls、token_summary、delivery）
- [x] `metrics.py` 新增 `get_run_llm_trace(run_dir)` 正确解析 llm-request.json 和 llm-response.json，提取 prompt 摘要和输出摘要
- [x] `metrics.py` 新增 `get_run_artifacts(run_dir)` 正确提取各阶段产物的结构化摘要
- [x] `metrics.py` 新增 `get_run_diff(run_dir, stage)` 正确读取并返回 diff 文件内容

## REST API 扩展

- [x] `GET /api/v1/metrics/active-run` 返回活跃运行 JSON 或 null
- [x] `GET /api/v1/metrics/runs/{run_id}/detail` 返回运行完整详情 JSON
- [x] `GET /api/v1/metrics/runs/{run_id}/llm-trace` 返回 LLM 推理链 JSON
- [x] `GET /api/v1/metrics/runs/{run_id}/artifacts` 返回产物摘要 JSON
- [x] `GET /api/v1/metrics/runs/{run_id}/diff?type={stage}` 返回 diff 文本内容
- [x] OpenAPI 规范中新增端点定义完整

## 前端页面布局

- [x] 三栏布局正确渲染：左侧栏（运行列表）+ 中央区（Pipeline 监控）+ 右侧栏（LLM 推理）
- [x] 无运行数据时显示引导空状态
- [x] 有活跃运行时自动聚焦
- [x] 无活跃运行时默认展示最近运行

## Pipeline Stepper

- [x] 6 阶段水平 Stepper 正确渲染
- [x] 各阶段状态指示正确（pending/running/success/failed/blocked）
- [x] running 状态有脉冲动画
- [x] 点击阶段节点可定位到对应详情

## 阶段详情面板

- [x] 阶段概览卡片正确展示状态、耗时、Token、Provider
- [x] 各阶段产物卡片展示正确的摘要字段
- [x] 代码 Diff 预览默认折叠，可展开
- [x] 审批卡片正确展示审批状态、决策人、时间、理由

## LLM 推理详情面板

- [x] System Prompt 摘要正确截取和展示
- [x] User Prompt 摘要正确截取和展示
- [x] 模型输出正确展示（支持 JSON 格式化）
- [x] Token 统计和调用耗时正确展示
- [x] 多次 LLM 调用以时间线形式展示

## 交付成果展示

- [x] 交付阶段展示变更摘要、验证证据、Git 状态、合并就绪状态
- [x] 交付 Diff 可预览

## 实时刷新

- [x] running 状态下每 3 秒自动轮询
- [x] 非 running 状态下每 10 秒轮询
- [x] 运行耗时每秒实时更新

## 清理与回归

- [x] 旧组件（StageStatsChart、RunsTrendChart、TokenUsageChart、KpiCards、RunDetailDialog）已删除
- [x] recharts 依赖已从 package.json 移除
- [x] 原有 API 端点（overview、stage-stats、token-usage、recent-runs、timeline）仍可正常访问
- [x] 现有测试套件全部通过（test_instant_confirmation 预存失败与本次变更无关）
