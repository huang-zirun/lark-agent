# Tasks

- [x] Task 1: 实现消息缓冲与合并机制
  - [x] SubTask 1.1: 在 `devflow/message_buffer.py` 中新增 `MessageBuffer` 类，支持按 `chat_id + sender_id` 分组缓冲消息，实现合并窗口计时和消息拼接
  - [x] SubTask 1.2: 在 `config.json` schema 中新增 `message_merge_window_seconds` 配置项（默认 5 秒）
  - [x] SubTask 1.3: 修改 `run_start_loop`，将事件流先经过 `MessageBuffer` 缓冲后再进入 `process_bot_event`
  - [x] SubTask 1.4: 缓冲窗口内收到后续消息时，回复"已追加到当前需求中"
  - [x] SubTask 1.5: 编写单元测试验证合并逻辑（窗口内合并、窗口外独立、多用户隔离）

- [x] Task 2: 实现按用户分组的消息队列
  - [x] SubTask 2.1: 在 `devflow/message_queue.py` 中新增 `UserMessageQueue` 类，按 `chat_id + sender_id` 分组管理消息队列，支持 `max_queue_size` 限制
  - [x] SubTask 2.2: 在 `config.json` schema 中新增 `max_queue_size` 配置项（默认 5）
  - [x] SubTask 2.3: 修改 `run_start_loop`，将 `process_bot_event` 改为按用户分组异步执行，同一用户串行、不同用户并行
  - [x] SubTask 2.4: 队列满时丢弃最早消息并回复提示
  - [x] SubTask 2.5: 编写单元测试验证队列逻辑（串行保证、并行隔离、队列溢出）

- [x] Task 3: 实现即时确认回复
  - [x] SubTask 3.1: 在 `process_bot_event` 入口处，解析事件后立即发送确认回复（"收到需求，正在分析中… 运行 ID：{run_id}"）
  - [x] SubTask 3.2: 检查点命令收到后立即回复确认（"收到指令，正在处理…"）
  - [x] SubTask 3.3: 确认回复使用幂等键防止重复
  - [x] SubTask 3.4: 编写集成测试验证确认回复时序

- [x] Task 4: 实现阶段状态通知
  - [x] SubTask 4.1: 在 `config.json` schema 中新增 `progress_notifications_enabled` 配置项（默认 true）
  - [x] SubTask 4.2: 定义阶段中文名映射表（`requirement_intake` → "需求分析"，`solution_design` → "方案设计" 等）
  - [x] SubTask 4.3: 在流水线阶段转换点插入状态通知发送逻辑
  - [x] SubTask 4.4: 阶段开始通知格式："📋 {阶段中文名} 进行中… （{已完成数}/{总数}）"
  - [x] SubTask 4.5: 阶段完成通知格式："✅ {阶段中文名} 已完成"
  - [x] SubTask 4.6: 阶段失败通知格式："❌ {阶段中文名} 失败：{错误摘要}"
  - [x] SubTask 4.7: 状态通知使用飞书消息回复，携带幂等键
  - [x] SubTask 4.8: 编写单元测试验证通知逻辑（启用/禁用、格式正确、幂等）

- [x] Task 5: 实现欢迎消息
  - [x] SubTask 5.1: 在 `config.json` schema 中新增 `default_chat_id` 配置项
  - [x] SubTask 5.2: 在 `run_start_loop` 中，事件监听启动前发送欢迎卡片
  - [x] SubTask 5.3: 构建欢迎卡片：标题"🤖 DevFlow 已就绪"、输入示例、命令列表、配置摘要
  - [x] SubTask 5.4: 未配置 `default_chat_id` 时跳过发送并记录日志
  - [x] SubTask 5.5: 编写单元测试验证欢迎消息内容和跳过逻辑

- [x] Task 6: 实现 `/help` 和 `/status` 命令
  - [x] SubTask 6.1: 在 `devflow/checkpoint.py` 的命令解析中新增 `/help`、`/帮助`、`/status`、`/状态` 识别
  - [x] SubTask 6.2: 实现 `/help` 处理逻辑：回复使用指引卡片，不创建运行
  - [x] SubTask 6.3: 实现 `/status` 处理逻辑：查找该用户的活跃运行，回复状态摘要或"无活跃任务"
  - [x] SubTask 6.4: 在消息路由优先级中将系统命令置于最高优先级
  - [x] SubTask 6.5: 编写单元测试验证命令解析和处理逻辑

- [x] Task 7: 集成测试与端到端验证
  - [x] SubTask 7.1: 验证多消息合并场景：用户 5 秒内发送 3 条消息，仅创建 1 个运行
  - [x] SubTask 7.2: 验证消息队列场景：运行处理中用户发送新消息，入队等待
  - [x] SubTask 7.3: 验证即时确认：消息发送后 2 秒内收到确认回复
  - [x] SubTask 7.4: 验证阶段通知：每个阶段转换时收到状态更新
  - [x] SubTask 7.5: 验证欢迎消息：启动后收到欢迎卡片
  - [x] SubTask 7.6: 验证 `/help` 和 `/status` 命令正常工作

# Task Dependencies

- [Task 2] depends on [Task 1]（消息队列需要先有缓冲合并机制）
- [Task 3] depends on [Task 1]（即时确认需要与缓冲合并协调）
- [Task 4] depends on [Task 3]（阶段通知需要确认回复的基础设施）
- [Task 5] independent
- [Task 6] independent
- [Task 7] depends on [Task 1, Task 2, Task 3, Task 4, Task 5, Task 6]
