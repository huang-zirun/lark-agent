# 飞书机器人体验打磨 V2 Spec

## Why

DevFlow 飞书机器人存在三类核心体验缺陷和若干细节问题：(1) 启动后机器人不主动发消息，用户面对空白对话不知是否已就绪；(2) 需求分析阶段产生的待澄清问题（open_questions）仅以摘要形式展示在 PRD 卡片中，用户无法回复，导致质量审查不通过后方案设计节点崩溃；(3) 中间产物文档（方案、评审报告等）仅展示摘要，用户无法查看完整内容，难以做出审批判断。此外，交互流程中还有多项体验细节需要从产品视角打磨。

## What Changes

- 修复启动后机器人不主动发消息的问题：确保 `devflow start` 启动后向用户可见地发送就绪消息
- 新增待澄清问题交互机制：需求分析完成后，如有待澄清问题，暂停流水线并展示问题卡片，等待用户回复后再继续
- 新增中间产物文档发布为飞书云文档：将方案文档、代码评审报告等关键中间产物发布为飞书云文档，在卡片中提供可点击链接
- 改进审批交互：支持简短 run_id 引用、提供更清晰的审批操作指引
- 改进错误恢复引导：失败时提供明确的恢复操作步骤
- 改进长操作反馈：LLM 调用期间发送"思考中"状态提示

## Impact

- Affected specs: 需求分析流程、检查点交互协议、文档发布机制
- Affected code:
  - `devflow/pipeline.py` — `process_bot_event`、`run_start_loop`、`maybe_run_solution_design`、`publish_requirement_prd`
  - `devflow/intake/lark_cli.py` — 新增文档发布函数
  - `devflow/prd.py` — PRD 卡片增加待澄清问题交互区域
  - `devflow/checkpoint.py` — 新增待澄清问题检查点类型
  - `devflow/config.py` — 新增文档发布相关配置

## ADDED Requirements

### Requirement: 启动就绪消息保障

系统 SHALL 在 `devflow start` 启动后确保用户能收到就绪消息，无论 `default_chat_id` 是否配置。

#### Scenario: 已配置 default_chat_id 时发送就绪消息
- **WHEN** `devflow start` 成功启动并开始监听事件
- **AND** `interaction.default_chat_id` 已配置
- **THEN** 系统 SHALL 向该聊天发送欢迎卡片
- **AND** 卡片 SHALL 包含机器人名称、功能简介、输入示例、可用命令

#### Scenario: 未配置 default_chat_id 时在控制台输出引导
- **WHEN** `devflow start` 成功启动并开始监听事件
- **AND** `interaction.default_chat_id` 未配置
- **THEN** 系统 SHALL 在控制台输出明确的引导信息
- **AND** 引导信息 SHALL 包含：机器人已就绪、用户可在飞书中向机器人发送消息、配置 default_chat_id 可启用主动欢迎消息的方法
- **AND** 系统 SHALL 在用户首次发消息时回复包含使用指引的确认消息

#### Scenario: 用户首次交互时发送引导
- **WHEN** 用户首次向机器人发送消息
- **AND** 之前未收到过欢迎消息（即 `default_chat_id` 未配置）
- **THEN** 系统 SHALL 在确认回复中附带简短的使用指引
- **AND** 指引格式为："收到！我是 DevFlow 机器人，发送需求描述即可启动开发流水线。发送 /help 查看完整指引。"

### Requirement: 待澄清问题交互机制

系统 SHALL 在需求分析产生待澄清问题时，暂停流水线并向用户展示可交互的问题卡片，等待用户回复后再继续方案设计。

#### Scenario: 存在待澄清问题时暂停并展示问题卡片
- **WHEN** 需求分析完成
- **AND** `quality.ready_for_next_stage` 为 `false`
- **AND** `open_questions` 列表非空
- **THEN** 系统 SHALL 暂停流水线，不自动进入方案设计阶段
- **AND** 系统 SHALL 向用户发送待澄清问题卡片
- **AND** 卡片 SHALL 逐条列出所有待澄清问题，每条标注序号
- **AND** 卡片 SHALL 包含操作指引："请回复问题的答案，或回复 `继续` 跳过澄清直接进入方案设计"

#### Scenario: 用户回复待澄清问题
- **WHEN** 用户回复了待澄清问题的答案
- **THEN** 系统 SHALL 将用户回答追加到需求的 `open_questions` 对应条目的 `answer` 字段
- **AND** 系统 SHALL 重新评估质量信号（更新 `completeness_score`、`ambiguity_score`、`ready_for_next_stage`）
- **AND** 系统 SHALL 回复"已收到你的回答，正在继续方案设计…"
- **AND** 系统 SHALL 继续执行方案设计阶段

#### Scenario: 用户选择跳过澄清
- **WHEN** 用户回复 `继续` 或 `skip` 或 `跳过`
- **THEN** 系统 SHALL 标记所有未回答的 open_questions 为 `skipped`
- **AND** 系统 SHALL 设置 `quality.ready_for_next_stage` 为 `true`（带警告）
- **AND** 系统 SHALL 继续执行方案设计阶段
- **AND** 方案设计检查点 SHALL 记录 `quality_at_approval` 包含跳过澄清的警告

#### Scenario: 无待澄清问题时正常流转
- **WHEN** 需求分析完成
- **AND** `quality.ready_for_next_stage` 为 `true`
- **OR** `open_questions` 列表为空
- **THEN** 系统 SHALL 不暂停，直接继续方案设计阶段

#### Scenario: 待澄清问题卡片格式
- **WHEN** 系统发送待澄清问题卡片
- **THEN** 卡片 SHALL 使用交互式卡片格式
- **AND** 卡片标题为 "🔍 需求待澄清"
- **AND** 卡片头部使用橙色模板
- **AND** 卡片内容区域逐条展示问题，格式为 "• Q{n}：{question}"
- **AND** 卡片底部展示操作指引

### Requirement: 中间产物文档发布为飞书云文档

系统 SHALL 将关键中间产物（方案文档、代码评审报告）发布为飞书云文档，并在交互卡片中提供可点击链接，使用户能查看完整内容。

#### Scenario: 方案文档发布为飞书云文档
- **WHEN** 方案设计完成并生成 `solution.md`
- **THEN** 系统 SHALL 将 `solution.md` 内容发布为飞书云文档
- **AND** 发布 SHALL 使用与 PRD 文档相同的 `docs +create` 机制
- **AND** 方案评审卡片 SHALL 包含方案文档的飞书链接
- **AND** 链接格式为 "[查看完整方案]({url})"

#### Scenario: 代码评审报告发布为飞书云文档
- **WHEN** 代码评审完成并生成 `code-review.md`
- **THEN** 系统 SHALL 将 `code-review.md` 内容发布为飞书云文档
- **AND** 代码评审卡片 SHALL 包含评审报告的飞书链接
- **AND** 链接格式为 "[查看完整评审报告]({url})"

#### Scenario: 文档发布失败时的降级处理
- **WHEN** 飞书云文档发布失败
- **THEN** 系统 SHALL 不阻塞流水线
- **AND** 卡片 SHALL 显示"完整文档发布失败，请查看本地产物：{local_path}"
- **AND** `run.json` SHALL 记录发布失败的错误信息

#### Scenario: PRD 卡片增加完整文档链接
- **WHEN** PRD 文档创建成功并返回 URL
- **THEN** PRD 预览卡片 SHALL 在顶部显眼位置展示 "[查看完整 PRD 文档]({url})" 链接
- **AND** 卡片摘要区域保留，作为快速预览

### Requirement: 审批交互改进

系统 SHALL 改进审批交互体验，降低用户操作门槛。

#### Scenario: 卡片中提供可复制的审批命令
- **WHEN** 系统发送方案评审或代码评审卡片
- **THEN** 卡片 SHALL 在操作指引区域提供可一键复制的审批命令
- **AND** 命令格式使用飞书代码块包裹，便于点击复制
- **AND** 同时提供同意和拒绝两种命令

#### Scenario: 支持简短 run_id 引用
- **WHEN** 用户发送审批命令
- **AND** 命令中的 run_id 是完整 run_id 的前缀且能唯一匹配
- **THEN** 系统 SHALL 接受该简短 run_id 作为有效引用
- **AND** 系统 SHALL 在回复中使用完整 run_id 以避免歧义

#### Scenario: 审批确认反馈
- **WHEN** 用户发送 Approve 或 Reject 命令
- **THEN** 系统 SHALL 在 2 秒内回复确认消息
- **AND** 确认消息 SHALL 包含操作类型和 run_id
- **AND** 格式为 "✅ 已收到同意指令，正在继续… 运行 ID：{run_id}" 或 "🔄 已收到拒绝指令，正在处理… 运行 ID：{run_id}"

### Requirement: 错误恢复引导改进

系统 SHALL 在流水线失败时提供明确的、可操作的恢复步骤。

#### Scenario: 需求分析失败时的恢复引导
- **WHEN** 需求分析阶段失败
- **THEN** 失败消息 SHALL 包含：错误原因、建议操作、重新发送需求的提示
- **AND** 格式为 "❌ 需求分析失败：{原因}\n💡 建议：{操作}\n🔄 请修改后重新发送需求描述。"

#### Scenario: 方案设计失败时的恢复引导
- **WHEN** 方案设计阶段失败
- **THEN** 失败消息 SHALL 包含：错误原因、建议操作
- **AND** 如果是 LLM 调用失败，建议 SHALL 包含"检查 LLM 配置和 API Key 是否有效"

#### Scenario: 代码生成失败时的恢复引导
- **WHEN** 代码生成阶段失败
- **AND** 失败原因是 QualityGateError
- **THEN** 失败消息 SHALL 包含质量门禁未通过的具体原因
- **AND** 建议 SHALL 包含"可尝试 Reject 后重新设计方案"

### Requirement: 长操作反馈改进

系统 SHALL 在 LLM 调用等长操作期间提供进度反馈，避免用户长时间无响应。

#### Scenario: LLM 调用开始时发送思考提示
- **WHEN** 系统开始 LLM 调用（需求分析、方案设计、代码生成等）
- **THEN** 系统 SHALL 在调用开始后发送"🤔 正在思考…"提示
- **AND** 提示 SHALL 包含当前阶段名称
- **AND** 格式为 "🤔 {阶段中文名}：正在思考…"

#### Scenario: LLM 调用超时提醒
- **WHEN** LLM 调用已持续超过 30 秒
- **THEN** 系统 SHALL 发送"⏳ 仍在处理中，请稍候…"提醒
- **AND** 该提醒 SHALL 最多发送一次，避免刷屏

#### Scenario: 思考提示可配置
- **WHEN** `interaction.progress_notifications_enabled` 为 `false`
- **THEN** 系统 SHALL 不发送思考提示和超时提醒

## MODIFIED Requirements

### Requirement: PRD 预览卡片

原卡片：摘要区域展示核心问题、目标、验收标准、待澄清问题的截断预览（最多 3 项）

修改为：
- 顶部新增"[查看完整 PRD 文档]({url})"链接区域
- 待澄清问题区域：如果存在未回答的 open_questions，使用橙色背景高亮展示，并标注"⚠️ 需要你的回复"
- 摘要区域保留，作为快速预览

### Requirement: 方案评审卡片

原卡片：展示方案摘要、文件变更预览、审批命令

修改为：
- 新增"[查看完整方案文档]({url})"链接
- 文件变更预览从最多 5 项增加到最多 10 项
- 审批命令使用代码块包裹，便于一键复制

### Requirement: 代码评审卡片

原卡片：展示评审摘要、问题预览、审批命令

修改为：
- 新增"[查看完整评审报告]({url})"链接
- 问题预览从最多 5 项增加到最多 10 项
- 审批命令使用代码块包裹，便于一键复制

### Requirement: 消息路由优先级

原优先级：系统命令（`/help`、`/status`）> 检查点命令 > 拒绝理由 > 仓库恢复 > 合并窗口判断 > 新需求

修改为：系统命令 > 检查点命令 > 拒绝理由 > 待澄清问题回复 > 仓库恢复 > 合并窗口判断 > 新需求

## REMOVED Requirements

无移除的需求。
