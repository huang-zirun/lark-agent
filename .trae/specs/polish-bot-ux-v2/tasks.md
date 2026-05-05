# Tasks

- [x] Task 1: 修复启动就绪消息保障
  - [x] SubTask 1.1: 修改 `_send_welcome_message`，当 `default_chat_id` 未配置时在控制台输出明确引导信息（机器人已就绪、用户可在飞书中向机器人发消息、配置 default_chat_id 可启用主动欢迎消息）
  - [x] SubTask 1.2: 在 `process_bot_event` 中新增首次交互检测逻辑：当 `default_chat_id` 未配置且用户首次发消息时，在确认回复中附带简短使用指引
  - [x] SubTask 1.3: 编写单元测试验证：未配置 default_chat_id 时控制台输出引导、首次交互附带指引

- [x] Task 2: 实现待澄清问题交互机制
  - [x] SubTask 2.1: 在 `devflow/checkpoint.py` 中新增 `build_clarification_checkpoint` 函数，创建 `stage=clarification`、`status=waiting_clarification` 的检查点
  - [x] SubTask 2.2: 在 `devflow/checkpoint.py` 中新增 `build_clarification_card` 函数，构建待澄清问题卡片（橙色头部、逐条列出问题、操作指引）
  - [x] SubTask 2.3: 修改 `devflow/pipeline.py` 的 `process_bot_event`，在需求分析完成后检查 `quality.ready_for_next_stage` 和 `open_questions`，如果需要澄清则暂停流水线、写入 clarification 检查点、发送问题卡片
  - [x] SubTask 2.4: 在 `devflow/checkpoint.py` 的 `parse_clarification_reply` 中识别用户回复：`继续`/`skip`/`跳过` 为跳过澄清，其他文本作为问题答案
  - [x] SubTask 2.5: 在 `devflow/pipeline.py` 的 `maybe_process_checkpoint_event` 中新增 `waiting_clarification` 状态的路由处理：匹配到澄清检查点后，将用户回答追加到需求 open_questions 的 answer 字段，重新评估质量信号，继续方案设计
  - [x] SubTask 2.6: 修改消息路由优先级，在检查点命令和仓库恢复之间插入待澄清问题回复路由
  - [x] SubTask 2.7: 编写单元测试验证：有 open_questions 时暂停并展示卡片、用户回复后继续、跳过澄清后继续、无 open_questions 时正常流转

- [x] Task 3: 中间产物文档发布为飞书云文档
  - [x] SubTask 3.1: 在 `devflow/intake/lark_cli.py` 中新增 `publish_document` 通用函数，封装 `docs +create --api-version v2 --as bot --doc-format markdown` 调用，返回 `{document_id, url}`
  - [x] SubTask 3.2: 修改 `devflow/pipeline.py` 的 `publish_solution_review_checkpoint`，在发送评审卡片前将 `solution.md` 发布为飞书云文档，将链接注入卡片
  - [x] SubTask 3.3: 修改 `devflow/pipeline.py` 的 `publish_code_review_checkpoint`，在发送评审卡片前将 `code-review.md` 发布为飞书云文档，将链接注入卡片
  - [x] SubTask 3.4: 修改 `devflow/prd.py` 的 `build_prd_preview_card`，在卡片顶部新增"[查看完整 PRD 文档]({url})"链接区域
  - [x] SubTask 3.5: 修改 `devflow/checkpoint.py` 的 `build_solution_review_card`，新增方案文档飞书链接、文件变更预览增加到 10 项、审批命令使用代码块
  - [x] SubTask 3.6: 修改 `devflow/checkpoint.py` 的 `build_code_review_card`，新增评审报告飞书链接、问题预览增加到 10 项、审批命令使用代码块
  - [x] SubTask 3.7: 文档发布失败时降级处理：卡片显示本地路径、run.json 记录错误
  - [x] SubTask 3.8: 编写单元测试验证：文档发布成功时卡片包含链接、发布失败时降级显示本地路径

- [x] Task 4: 审批交互改进
  - [x] SubTask 4.1: 修改 `devflow/checkpoint.py` 的 `parse_checkpoint_command`，支持 run_id 前缀匹配：当输入的 run_id 不是完整 ID 时，在 `artifacts/runs/` 下搜索前缀匹配的运行目录
  - [x] SubTask 4.2: 修改审批确认回复格式，包含操作类型和完整 run_id："✅ 已收到同意指令，正在继续… 运行 ID：{run_id}"
  - [x] SubTask 4.3: 编写单元测试验证：前缀匹配逻辑、确认回复格式

- [x] Task 5: 错误恢复引导改进
  - [x] SubTask 5.1: 修改 `devflow/pipeline.py` 的 `build_failure_reply`，按阶段类型提供差异化恢复引导：需求分析失败建议补充上下文、方案设计失败建议检查 LLM 配置、代码生成 QualityGateError 建议 Reject 后重做
  - [x] SubTask 5.2: 修改 `send_stage_notification` 的失败通知格式，增加建议操作
  - [x] SubTask 5.3: 编写单元测试验证：各阶段失败消息包含对应建议

- [x] Task 6: 长操作反馈改进
  - [x] SubTask 6.1: 在 `devflow/pipeline.py` 中新增 `send_thinking_notification` 函数，发送"🤔 {阶段中文名}：正在思考…"提示
  - [x] SubTask 6.2: 在 LLM 调用开始前（需求分析、方案设计、代码生成、测试生成、代码评审）插入思考提示发送
  - [x] SubTask 6.3: 新增超时提醒逻辑：LLM 调用超过 30 秒时发送"⏳ 仍在处理中，请稍候…"，每个阶段最多发送一次
  - [x] SubTask 6.4: 思考提示和超时提醒受 `progress_notifications_enabled` 配置控制
  - [x] SubTask 6.5: 编写单元测试验证：思考提示格式、超时提醒逻辑、配置关闭时不发送

- [x] Task 7: 集成测试与端到端验证
  - [x] SubTask 7.1: 验证启动就绪消息：未配置 default_chat_id 时控制台输出引导、首次交互附带指引
  - [x] SubTask 7.2: 验证待澄清问题交互：有 open_questions 时暂停、用户回复后继续、跳过后继续
  - [x] SubTask 7.3: 验证中间产物文档发布：方案和评审报告卡片包含飞书链接
  - [x] SubTask 7.4: 验证审批交互：前缀匹配、确认反馈格式
  - [x] SubTask 7.5: 验证错误恢复引导：各阶段失败消息包含建议
  - [x] SubTask 7.6: 验证长操作反馈：思考提示和超时提醒

# Task Dependencies

- [Task 2] depends on [Task 1]（待澄清问题交互需要与首次交互指引协调消息路由）
- [Task 3] depends on [Task 2]（文档发布需要在澄清交互完成后才能正确展示完整链接）
- [Task 4] independent
- [Task 5] independent
- [Task 6] independent
- [Task 7] depends on [Task 1, Task 2, Task 3, Task 4, Task 5, Task 6]
