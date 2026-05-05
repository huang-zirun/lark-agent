# 飞书机器人体验打磨 V2 实施记录

Date: 2026-05-05
Spec: d:\lark\.trae\specs\polish-bot-ux-v2

## 问题背景

DevFlow 飞书机器人存在三类核心体验缺陷：

1. **启动后机器人不主动发消息** — 用户面对空白对话不知是否已就绪
2. **待澄清问题不显示、用户无法回复** — 需求分析阶段产生的 open_questions 仅以摘要形式展示在 PRD 卡片中，用户无法回复，导致质量审查不通过后方案设计节点崩溃
3. **中间文档只能看摘要** — 方案、评审报告等中间产物仅展示摘要，用户无法查看完整内容

## 实施内容

### Task 1: 启动就绪消息保障

**修改文件**: [pipeline.py](file:///d:/lark/devflow/pipeline.py)

- 新增 `_print_no_default_chat_guidance()`：未配置 `default_chat_id` 时在控制台输出英文引导信息（避免 Windows 终端 GBK 编码乱码问题）
- 新增首次交互检测：用户首次发消息时附带使用指引
- 新增测试: [test_welcome_message.py](file:///d:/lark/tests/test_welcome_message.py) `FirstInteractionGuideTests`

**编码修复**: Windows 终端默认使用 GBK 编码，中文字符输出会出现乱码。将控制台引导信息改为英文，确保在所有终端环境下都能正确显示。

### Task 2: 待澄清问题交互机制

**修改文件**: [checkpoint.py](file:///d:/lark/devflow/checkpoint.py), [pipeline.py](file:///d:/lark/devflow/pipeline.py)

- 新增 `ClarificationReply` 数据类、`parse_clarification_reply()` 识别跳过/回答
- 新增 `build_clarification_checkpoint()`、`build_clarification_card()` 构建橙色"🔍 需求待澄清"卡片
- 修改 `process_bot_event()`：需求分析后检查 `ready_for_next_stage` 和 `open_questions`，需要澄清时暂停流水线
- 新增 `resume_from_clarification()`：处理用户回答追加、质量重评、跳过标记
- 新增测试: [test_clarification.py](file:///d:/lark/tests/test_clarification.py)

### Task 3: 中间产物文档发布

**修改文件**: [lark_cli.py](file:///d:/lark/devflow/intake/lark_cli.py), [pipeline.py](file:///d:/lark/devflow/pipeline.py), [prd.py](file:///d:/lark/devflow/prd.py), [checkpoint.py](file:///d:/lark/devflow/checkpoint.py)

- 新增 `publish_document()` 通用函数，封装 `docs +create` 发布飞书云文档
- 方案/代码评审卡片包含"[查看完整方案/评审报告]"飞书链接
- PRD 卡片顶部包含"[查看完整 PRD 文档]"链接
- 文件变更/问题预览从 5 项增加到 10 项
- 发布失败时降级显示本地路径
- 新增测试: [test_prd_publish.py](file:///d:/lark/tests/test_prd_publish.py)

### Task 4: 审批交互改进

**修改文件**: [checkpoint.py](file:///d:/lark/devflow/checkpoint.py), [pipeline.py](file:///d:/lark/devflow/pipeline.py)

- 新增 `resolve_run_id_prefix()` 支持 run_id 前缀匹配
- 新增 `PrefixMatchError` 处理歧义匹配
- 审批确认回复格式："✅ 已收到同意指令，正在继续… 运行 ID：{run_id}"
- 新增测试: [test_checkpoint.py](file:///d:/lark/tests/test_checkpoint.py) `ResolveRunIdPrefixTests`, `ParseCheckpointCommandPrefixTests`, `ConfirmationReplyFormatTests`

### Task 5: 错误恢复引导

**修改文件**: [pipeline.py](file:///d:/lark/devflow/pipeline.py)

- 新增 `_stage_failure_suggestion()` 按阶段返回差异化建议
- 失败通知格式增加 "💡 {建议}"
- 新增测试: [test_pipeline_start.py](file:///d:/lark/tests/test_pipeline_start.py) `StageFailureSuggestionTests`, `BuildFailureReplySuggestionTests`

### Task 6: 长操作反馈

**修改文件**: [pipeline.py](file:///d:/lark/devflow/pipeline.py)

- 新增 `send_thinking_notification()` 发送"🤔 {阶段中文名}：正在思考…"
- 新增 `ThinkingTimer` 类，30 秒超时后发送"⏳ 仍在处理中，请稍候…"
- 在 5 个 LLM 调用前插入思考提示（需求分析、方案设计、代码生成、测试生成、代码评审）
- 受 `progress_notifications_enabled` 配置控制
- 新增测试: [test_stage_notifications.py](file:///d:/lark/tests/test_stage_notifications.py) `ThinkingNotificationFormatTests`, `ThinkingTimerTests`

## 测试结果

**150 个测试全部通过**：
- test_welcome_message.py: 15 passed
- test_checkpoint.py: 21 passed  
- test_clarification.py: 16 passed
- test_prd_publish.py: 21 passed
- test_stage_notifications.py: 40 passed
- test_pipeline_start.py: 37 passed

## 关键设计决策

1. **待澄清问题交互流程**：需求分析 → 检查 ready_for_next_stage → 如需要澄清则写入 checkpoint (status=waiting_clarification) → 发送卡片 → 等待用户回复 → 恢复后重新评估质量 → 继续方案设计

2. **文档发布降级策略**：发布失败不阻塞流水线，卡片显示本地路径，run.json 记录错误

3. **消息路由优先级**：系统命令 > 检查点命令 > 拒绝理由 > 待澄清问题回复 > 仓库恢复 > 合并窗口判断 > 新需求

## 后续改进方向

- 待澄清问题支持逐条回答（当前实现是一次性回答所有问题）
- 思考提示和超时提醒支持自定义间隔时间
- 文档发布支持指定目标文件夹（当前使用 prd_folder_token）
