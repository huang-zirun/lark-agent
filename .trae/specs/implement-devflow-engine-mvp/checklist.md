# DevFlow Engine MVP Checklist

## 项目基础设施
- [ ] 后端 `pyproject.toml` 存在且包含所有必要依赖
- [ ] 所有 `__init__.py` 包文件存在
- [ ] `uv run uvicorn app.main:app --reload` 可启动 FastAPI 服务
- [ ] `/docs` 可访问 Swagger UI
- [ ] `/api/health` 返回 200，包含 service、status、version、time 字段
- [ ] 前端 `package.json` 存在且包含所有必要依赖
- [ ] `npm run dev` 可启动 Vite 开发服务器
- [ ] 浏览器可访问前端首页

## 数据库层
- [ ] SQLite 数据库文件自动创建
- [ ] pipeline_run、stage_run、artifact、checkpoint_record、workspace、provider_config 表自动创建
- [ ] 数据可持久化，重启后可查询

## 领域模型
- [ ] PipelineTemplate 模型包含 id、name、description、version、template_kind、stages、entry_stage_key、default_provider_id 字段
- [ ] PipelineRun 模型包含 id、template_id、workspace_ref_id、requirement_text、status、current_stage_key 字段
- [ ] StageDefinition 模型包含 key、name、stage_type、depends_on、agent_profile_id、approve_target、reject_target 字段
- [ ] StageRun 模型包含 id、run_id、stage_key、status、attempt、input_artifact_refs、output_artifact_refs 字段
- [ ] Artifact 模型包含 id、run_id、stage_run_id、artifact_type、schema_version、content_summary、storage_uri 字段
- [ ] CheckpointRecord 模型包含 id、run_id、stage_key、checkpoint_type、status、decision_by、reason 字段
- [ ] Workspace 模型包含 id、run_id、source_repo_path、workspace_path、git_commit_at_create、status 字段
- [ ] ProviderConfig 模型包含 id、name、provider_type、api_base、api_key_encrypted、default_model、enabled 字段

## Schema 校验
- [ ] requirement_brief Schema 校验通过（goal、acceptance_criteria、constraints、assumptions、risks）
- [ ] design_spec Schema 校验通过（summary、affected_files、test_strategy、risks）
- [ ] change_set Schema 校验通过（files 数组，每个含 path、change_type、patch）
- [ ] diff_manifest Schema 校验通过（base_commit、changed_files、diff_path、stats）
- [ ] test_report Schema 校验通过（exit_code、stdout、stderr、duration_ms、summary）
- [ ] review_report Schema 校验通过（recommendation、scores、issues、summary）
- [ ] delivery_summary Schema 校验通过（status、deliverables、test_summary、known_risks、next_steps）

## Pipeline 状态机
- [ ] PipelineRun 状态转换：draft → ready → running → waiting_checkpoint → running → succeeded
- [ ] PipelineRun 异常转换：running → failed、任意 → terminated
- [ ] PipelineRun 暂停/恢复：running → paused → running
- [ ] StageRun 状态转换：pending → running → succeeded
- [ ] StageRun 失败重试：running → failed → retrying → running
- [ ] 非法状态转换被拒绝并抛出异常

## Pipeline Orchestrator
- [ ] feature_delivery_default 模板包含 8 个阶段定义
- [ ] 创建 PipelineRun 后状态为 draft
- [ ] 预检通过后状态为 ready
- [ ] 启动后阶段顺序推进
- [ ] 遇到 checkpoint 阶段时暂停等待审批

## Checkpoint 机制
- [ ] checkpoint_design_approval 等待人工审批
- [ ] Approve 后跳转到 approve_target（code_generation）
- [ ] Reject 后跳转到 reject_target（solution_design），reason 被保存
- [ ] checkpoint_final_approval 等待人工审批
- [ ] Reject reason 可被后续阶段读取

## Artifact Store
- [ ] 小 JSON（< 10KB）直接存入 SQLite
- [ ] 大文本（>= 10KB）存入文件系统，URI 引用存入 SQLite
- [ ] artifacts/{run_id}/stage_{stage_key}/ 目录结构正确
- [ ] 通过 API 可查询和读取所有 Artifact

## Workspace Manager
- [ ] 可注册本机 Git 仓库路径
- [ ] 注册时验证路径存在且为 Git 仓库
- [ ] PipelineRun 启动时创建隔离 workspace
- [ ] Agent 变更仅发生在隔离目录
- [ ] 可生成 diff_manifest

## Patch Applier
- [ ] 可在 workspace 中 apply unified diff 格式的 patch
- [ ] patch apply 失败时最多重试 2 次
- [ ] apply 成功后生成 diff_manifest

## Command Runner
- [ ] 可执行测试命令
- [ ] 捕获 stdout、stderr、exit_code、duration_ms
- [ ] 测试失败不阻塞 Pipeline

## Provider Registry
- [ ] Mock Provider 返回固定输出
- [ ] OpenAI-compatible Provider 支持 api_base、api_key、model 配置
- [ ] Anthropic Provider 支持 api_key、model 配置
- [ ] Provider validate API 可验证连通性
- [ ] PipelineRun 可指定 provider_selection_override

## Agent 实现
- [ ] Mock Agent 可完整跑通 8 个阶段，不依赖 LLM
- [ ] Requirement Agent 输出符合 requirement_brief Schema
- [ ] Design Agent 输出符合 design_spec Schema
- [ ] Code Patch Agent 输出符合 change_set Schema
- [ ] Test Agent 输出符合 test_report Schema
- [ ] Review Agent 输出符合 review_report Schema
- [ ] Delivery Agent 输出符合 delivery_summary Schema

## REST API
- [ ] POST /api/pipelines 创建 PipelineRun
- [ ] GET /api/pipelines 列表查询
- [ ] GET /api/pipelines/{id} 详情查询
- [ ] POST /api/pipelines/{id}/start 启动
- [ ] POST /api/pipelines/{id}/pause 暂停
- [ ] POST /api/pipelines/{id}/resume 恢复
- [ ] POST /api/pipelines/{id}/terminate 终止
- [ ] GET /api/pipelines/{id}/timeline 时间线
- [ ] POST /api/checkpoints/{id}/approve 审批通过
- [ ] POST /api/checkpoints/{id}/reject 审批拒绝
- [ ] GET /api/artifacts/{id} 获取产物
- [ ] GET /api/pipelines/{id}/artifacts 获取 Run 所有产物
- [ ] POST /api/workspaces 注册仓库
- [ ] GET /api/workspaces 列表
- [ ] GET /api/workspaces/{id} 详情
- [ ] GET /api/workspaces/{id}/diff 查看 diff
- [ ] GET /api/providers 列表
- [ ] POST /api/providers 创建
- [ ] PUT /api/providers/{id} 更新
- [ ] POST /api/providers/{id}/validate 验证

## 前端控制台
- [ ] Pipeline 列表页可显示所有 PipelineRun
- [ ] Pipeline 列表页支持状态筛选
- [ ] Pipeline 详情页显示时间线视图
- [ ] Pipeline 详情页展示各阶段状态和产物
- [ ] Checkpoint 审批面板展示上下文
- [ ] Checkpoint 审批面板支持 Approve/Reject 操作
- [ ] Diff 查看器显示代码变更对比
- [ ] Artifact 查看器结构化展示产物

## 端到端演示
- [ ] Mock Agent 完整闭环可运行
- [ ] 两个 Checkpoint 的 Approve 流程正确
- [ ] Reject 回退后 Agent 可读取 Reject reason
- [ ] 自举演示：输入需求后完整跑通 Pipeline

## 错误处理
- [ ] 输入错误返回 400
- [ ] 预检错误 Run 保持 draft
- [ ] 执行错误 StageRun 标记 failed
- [ ] 系统错误返回 500

## 安全
- [ ] Agent 不直接修改原始仓库
- [ ] API Key 加密存储
