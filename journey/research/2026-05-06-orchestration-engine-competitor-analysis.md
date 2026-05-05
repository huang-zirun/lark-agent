# 竞品调研：Celia-veey/orchestration-engine

> 调研日期：2026-05-06
> 仓库地址：https://github.com/Celia-veey/orchestration-engine
> 赛道确认：飞书 AI 产品创新赛道 · 课题三：基于 AI 驱动的需求交付流程引擎

---

## 1. 项目确认依据

1. `main_api.py` 中 FastAPI 应用标题为 `"DevFlow Engine API"`，描述为 `"AI驱动的需求交付流程引擎RESTful API"`
2. `COLLABORATION_GUIDE.md` 标题为 `"DevFlow Engine 协作开发指南"`
3. `pipeline_engine.py` 实现完整 6 阶段状态机：需求分析 → 架构设计 → 人工检查点1 → 代码生成 → 测试生成 → 代码评审 → 人工检查点2 → 交付集成
4. 代码引用 `agents/real/` 下的真实 Agent（PMAgent, ArchitectAgent, CoderAgent, QAAgent, ReviewerAgent, DeliveryAgent）
5. 仓库有 `.trae/` 和 `.agents/` 目录，使用 Trae IDE 辅助开发
6. 最近 commit 分支名为 `devflow-engine-v2`

## 2. 团队信息

- 至少 2 人协作：Celia-veey + zegator
- 角色分工：角色 A（引擎架构师，负责状态机/API/检查点/工具链）、角色 B（AI 算法与提示词工程师，负责 Prompt/索引/自动回归/质量评估）
- 协作模式：A 先用 Mock 跑通主干，B 并行调试 Agent，最后联调

## 3. 项目结构

```
orchestration-engine/
├── .agents/                  # Trae agent 配置
├── .trae/                    # Trae IDE 配置
├── agents/
│   ├── __init__.py           # Agent 基类和注册
│   ├── pm_mock.py            # PM Mock Agent
│   ├── architect_mock.py     # Architect Mock Agent
│   ├── coder_mock.py         # Coder Mock Agent
│   ├── qa_mock.py            # QA Mock Agent
│   ├── reviewer_mock.py      # Reviewer Mock Agent
│   ├── delivery_mock.py      # Delivery Mock Agent
│   └── real/                 # 真实 Agent 实现（LLM 驱动）
├── Multi-Agents/
│   ├── agents/               # Agent 参考文档（references/）
│   └── skills/               # Agent SKILL.md（真实 Agent 的 Prompt）
├── skills/                   # Mock Agent 的 SKILL.md（固定模板）
│   ├── PM/SKILL.md
│   ├── Architect/SKILL.md
│   ├── Coder/SKILL.md
│   ├── QA/SKILL.md
│   ├── Reviewer/SKILL.md
│   ├── Delivery/SKILL.md
│   └── pr-creator/SKILL.md
├── pipeline_engine.py        # 核心编排器（49KB，最大文件）
├── main_api.py               # FastAPI REST API
├── models.py                 # Pydantic 数据模型
├── llm_client.py             # LLM 客户端
├── data_extractor.py         # JSON/Markdown 内容提取
├── file_tools.py             # 文件写入工具
├── reference_tools.py        # 参考文档按需加载
├── COLLABORATION_GUIDE.md    # 协作开发指南
├── .env.example              # 环境变量模板
└── requirements.txt          # Python 依赖
```

## 4. 核心架构分析

### 4.1 Pipeline 编排：自研状态机

```python
class PipelineStateEnum(str, Enum):
    INIT = "init"
    REQUIREMENT_ANALYSIS = "requirement_analysis"
    ARCHITECTURE_DESIGN = "architecture_design"
    HUMAN_APPROVAL_1 = "human_approval_1"
    CODE_GENERATION = "code_generation"
    TEST_GENERATION = "test_generation"
    CODE_REVIEW = "code_review"
    HUMAN_APPROVAL_2 = "human_approval_2"
    DELIVERY = "delivery"
    COMPLETED = "completed"
    FAILED = "failed"
```

- 11 个枚举值（6 阶段 + 2 检查点 + init/completed/failed）
- 状态切换通过 `set_state()` 方法，每次切换自动保存 `context.json`
- 断点恢复通过 `_restore_from_context(context_file)` 从 context.json 重建状态
- 缺少图可视化、条件边、并行执行等高级能力

### 4.2 Agent 实现：Mock + Real 双模式

**Mock Agent**（`agents/*_mock.py`）：
- 基于 `SkillManager` 读取 `skills/*/SKILL.md` 中的固定模板
- 不调用 LLM，0 成本跑通完整 Pipeline
- 用于快速验证主干流程

**Real Agent**（`agents/real/`）：
- 通过 `LLMClient` 调用 OpenAI-compatible API
- 使用 `Multi-Agents/skills/*/SKILL.md` 作为 System Prompt
- 支持多轮对话和工具调用

**切换方式：** `PipelineEngine(use_real_agents=True/False)`

### 4.3 SkillManager — 渐进式 Prompt 加载

```python
class SkillManager:
    def __init__(self, skills_dir="skills"):
        self.skill_index = {}   # 技能元数据索引
        self.skill_cache = {}   # 技能内容缓存
        self._build_skill_index()
    
    def _build_skill_index(self):
        # 只读取 SKILL.md 前 4KB，提取 YAML 头部
        ...
    
    def get_skill_prompt(self, skill_name):
        # 首次使用才加载完整内容，后续从缓存读取
        ...
```

- SKILL.md 格式：YAML front matter（name/description/tags/version）+ Markdown 正文（System Prompt）
- 启动时只建轻量索引，不加载内容
- 首次使用时加载全文并缓存

### 4.4 上下文模型：Pydantic 单体

```python
class PipelineContext(BaseModel):
    # 基础信息
    pipeline_id: str
    user_query: str
    state: PipelineStateEnum
    created_at: str
    updated_at: str
    
    # 阶段1：需求分析输出
    pm_result: Optional[Dict[str, Any]]
    template_report_md: Optional[str]
    template_report_path: Optional[str]
    
    # 阶段2：架构设计输出
    architect_result: Optional[Dict[str, Any]]
    plan_md: Optional[str]
    plan_md_path: Optional[str]
    file_change_list: Optional[List[Dict[str, Any]]]
    api_design: Optional[List[Dict[str, Any]]]
    
    # 人工检查点1
    approval_1_status: Optional[str]
    approval_1_reason: Optional[str]
    
    # 阶段3-6 类似...
    
    # 配置
    output_dir: str
    codebase_dir: str
    
    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}
```

- 所有阶段字段在一个 Pydantic 类中（~30 个字段）
- `extra="allow"` 允许额外字段，方便扩展
- 序列化/反序列化通过 Pydantic 的 `model_dump_json()` / `model_validate_json()`
- 每次状态切换自动 `save_to_file()`

### 4.5 LLM 客户端

```python
class LLMClient:
    def __init__(self, provider="openai", model=None):
        self.model = model or os.getenv("MODEL_NAME", "gpt-3.5-turbo")
        self.api_key = os.getenv(f"{provider.upper()}_API_KEY")
        self.base_url = os.getenv(f"{provider.upper()}_BASE_URL")
        self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=300.0)
    
    def chat_completion_json(self, messages, ...):
        # 三层 JSON 提取兜底：
        # 1. <json_output>...</json_output> 标签
        # 2. ```json ... ``` 代码块
        # 3. { ... } 花括号匹配
        ...
```

- 仅支持 OpenAI-compatible 接口
- JSON 输出用 `<json_output>` 标签约束 + 三层兜底解析
- 5 分钟超时，支持长代码生成
- 不支持运行时 Provider 切换

### 4.6 Human-in-the-Loop 检查点

```python
class ApprovalEvent:
    def __init__(self):
        self.event = asyncio.Event()
        self.action = None
        self.reason = None
    
    def set_approval(self, action, reason=""):
        self.action = action
        self.reason = reason
        self.event.set()
    
    async def wait(self):
        await self.event.wait()
        return self.action, self.reason
```

- 2 个检查点：方案审批（HUMAN_APPROVAL_1）+ 代码审批（HUMAN_APPROVAL_2）
- 审批通过 `asyncio.Event` 异步等待
- API: `POST /pipeline/{pipeline_id}/approve` 唤醒
- Reject 行为：
  - 检查点1 reject → 重跑需求分析（回到阶段1）
  - 检查点2 reject → 重跑代码生成+测试（回到阶段3），while True 循环直到 approve
- 无飞书审批集成

### 4.7 API 设计

```python
app = FastAPI(title="DevFlow Engine API", version="1.0.0")

POST /pipeline/trigger           # 触发新流水线（后台异步运行）
GET  /pipeline/{id}/status       # 查询流水线状态
POST /pipeline/{id}/approve      # 提交审批结果
GET  /pipeline/list              # 查询流水线列表
GET  /                           # API 根路径
```

- FastAPI + uvicorn，异步架构
- `BackgroundTasks` 运行流水线
- `PipelineManager` 管理所有流水线实例和审批事件
- 自动生成 Swagger UI 文档

### 4.8 参考文档体系

```python
def read_reference_doc(topic: str, section: str = None) -> str:
    """按需加载参考文档，截断到 2000 字符"""
    ref_map = {
        "ears-requirements": "ears-requirements.md",
        "three-layer-architecture": "three-layer-architecture.md",
        "adr-template": "adr-template.md",
        "nfr-checklist": "nfr-checklist.md",
        "git-conventions": "git-conventions.md",
        "api-design": "api-design.md",
        "db-schema": "db-schema.md",
        "auth-flow": "auth-flow.md",
        "tech-selection": "technology-selection.md",
        "environment-management": "environment-management.md",
        "testing-strategy": "testing-strategy.md",
        "django-best-practices": "django-best-practices.md",
        "release-checklist": "release-checklist.md",
    }
    ...
```

- 13 个行业规范文档，Agent 按需获取
- 截断到 2000 字符避免 token 浪费
- 支持按章节提取（`_extract_section()`）
- 架构师 Agent 在设计阶段参考行业规范

### 4.9 需求澄清多轮对话

```python
# pipeline_engine.py run_requirement_analysis()
max_rounds = 3
for round_num in range(max_rounds):
    pm_result = self.pm_agent.run(current_query, chat_history)
    if pm_result.get("type") == "clarification":
        questions = pm_result.get("questions", [])
        # 展示结构化问题（含选项、默认值、影响说明）
        for q in questions:
            print(f"Q{q['id']}: {q['question']}")
            for o in q.get("options", []):
                print(f"  {o['value']}. {o['label']}")
            print(f"  影响: {q.get('impact', '')}")
        # 用户回答后继续对话
        chat_history.append(...)
    else:
        # type == "solution"，需求已清晰
        break
```

- PM Agent 最多 3 轮澄清
- 每轮返回结构化问题：id / question / options / default_choice / impact
- 用户回答后加入 chat_history 继续对话
- 需求清晰后返回 solution

### 4.10 阶段耗时统计

```python
def _log_stage_start(self, stage_name, stage_desc):
    self.stage_start_time[stage_name] = time.time()
    ...

def _log_stage_end(self, stage_name, success=True, extra_msg=""):
    start_time = self.stage_start_time.get(stage_name, time.time())
    duration = round(time.time() - start_time, 2)
    ...
```

- 每个阶段独立计时
- 日志输出包含耗时信息

## 5. 与本项目对比

| 维度 | orchestration-engine | 本项目 (DevFlow Engine) | 优势方 |
|------|---------------------|------------------------|--------|
| Pipeline 编排 | 自研状态机 | LangGraph | **本项目**（图可视化、条件边、并行） |
| Agent 成熟度 | Mock + Real 双模式 | 6 个真实 Agent + 启发式分析 | 平手 |
| 飞书集成 | 无 | lark-cli WebSocket + 飞书审批 + PRD 文档 | **本项目** |
| 语义索引 | 无（参考文档替代） | AST 语义索引 | **本项目** |
| 自动修复 | max_retries=3 无限循环 | 1 次自动修复 + 人工兜底 | **本项目** |
| LLM Provider | 单 Provider | 5 Provider + 运行时切换 | **本项目** |
| API 框架 | FastAPI（异步） | stdlib HTTPServer（同步） | **对方** |
| 数据模型 | Pydantic 单体 | 版本化 JSON 契约 | **本项目**（更工程化） |
| 参考文档 | 13 个行业规范文档 | 无 | **对方** |
| 需求澄清 | 多轮对话（最多3轮） | 一次性分析 | **对方** |
| Mock 支持 | 完整 Mock Agent 层 | 仅启发式分析 | **对方** |
| 可观测性 | 无 | 实时仪表板 + Swagger/ReDoc | **本项目** |
| 审批通道 | 仅 API | 飞书审批 + Bot 消息双通道 | **本项目** |
| 审批机制 | asyncio.Event 异步等待 | 文件轮询 | **对方** |
| 阶段耗时 | 有统计 | 无 | **对方** |
| 日志系统 | 统一格式 | 各 Agent 独立 print | **对方** |
| 协作模式 | 2 人分工 | 1 人 + AI 辅助 | **对方**（团队） |

## 6. 可借鉴点（按优先级）

### P0 — 比赛冲刺必做

1. **Mock Agent 层**：6 个 `*_mock.py`，返回固定 JSON 契约格式产物，CLI 加 `--mock` 全局标志。演示时秒级跑通全链路，0 token 消耗。
2. **需求澄清多轮对话**：PM Agent 返回 `type: "clarification"` 带结构化问题，飞书 Bot 通过交互卡片实现多轮澄清。差异化亮点，评委可感知。

### P1 — 近期建议

3. **参考文档体系**：`devflow/references/` 放入 EARS/ADR/NFR/API 设计等精简规范，方案设计和代码评审 Agent 按需注入。
4. **阶段耗时统计**：`run.json` 中增加 `stage_metrics`，演示时展示各阶段耗时分布。
5. **统一日志系统**：`devflow/logger.py`，双输出（文件+控制台），统一格式。

### P2 — 锦上添花

6. **Skill/Prompt 外置管理**：Prompt 从代码中抽到 `devflow/skills/*/SKILL.md`，运行时按需加载，支持热更新。
7. **asyncio.Event 审批机制**：API 层异步等待，与飞书审批 webhook 回调天然契合。
8. **Reject 回滚策略配置化**：允许用户选择 reject 后回退到哪个阶段。

### P3 — 文档完善

9. **协作开发指南**：`docs/` 下增加 Agent 接口契约汇总文档。

## 7. 技术细节备忘

### JSON 解析三层兜底（对方实现）

```python
# 1. <json_output> 标签
json_match = re.search(r'<json_output>\s*(.*?)\s*</json_output>', content, re.DOTALL)
# 2. markdown 代码块
code_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
# 3. 花括号匹配（贪婪，有边界风险）
brace_match = re.search(r'\{.*\}', content, re.DOTALL)
```

**注意：** 第 3 层的 `r'\{.*\}'` 贪婪匹配有边界问题，可能匹配到错误的 JSON。本项目之前也踩过类似坑。

### 参考文档截断策略

```python
MAX_DOC_LENGTH = 2000
if len(content) > MAX_DOC_LENGTH:
    content = content[:MAX_DOC_LENGTH] + "\n\n... (document truncated, request specific sections if needed)"
```

简单粗暴但有效，避免消耗过多 token。

### Agent 接口标准（对方定义）

| Agent | 输入 | 输出 type |
|-------|------|-----------|
| PM | user_query, chat_history | clarification / solution |
| Architect | requirement_doc, codebase_context, chat_history | tool_call / solution |
| Coder | tech_plan, codebase_context, fix_hint | code_files + test_cases |
| QA | code_changes, requirement_doc | test_cases + execution_result |
| Reviewer | code_changes, tech_plan, test_result | review_summary + problem_list |
| Delivery | code_changes, test_result, review_score, requirement | branch_operation + pr_info |
