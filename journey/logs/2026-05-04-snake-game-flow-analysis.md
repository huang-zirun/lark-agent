# 飞书输入"创建一个贪吃蛇小游戏"的完整流程传递分析

## 用户输入

```
创建一个贪吃蛇小游戏 html 网页单机游戏
```

---

## 阶段一：输入检测与解析

**触发**：`devflow start` 监听飞书机器人消息事件

**输入检测** ([pipeline.py:105-119](file:///d:/lark/devflow/pipeline.py#L105-L119))：

```python
def detect_requirement_input(text: str) -> DetectedInput:
    # 1. 检查文档 URL → 不匹配
    # 2. 检查文档 Token → 不匹配
    # 3. 检查消息 ID → 不匹配
    # 4.  fallback 到 inline_text
    return DetectedInput(kind="inline_text", value="创建一个贪吃蛇小游戏 html 网页单机游戏")
```

**检测结果**：
- `kind`: `inline_text`
- `value`: `创建一个贪吃蛇小游戏 html 网页单机游戏`

---

## 阶段二：流水线运行初始化

**创建运行目录** ([pipeline.py:146-171](file:///d:/lark/devflow/pipeline.py#L146-L171))：

```
artifacts/runs/20260504T123000Z-om_evt-xxxxxxxx/
├── run.json          # 流水线运行记录
├── trace.jsonl       # 审计追踪（实时写入）
└── （后续阶段产物）
```

**初始 stages 状态**：
```json
[
  {"name": "requirement_intake", "status": "running"},
  {"name": "solution_design", "status": "pending"},
  {"name": "code_generation", "status": "pending"},
  {"name": "test_generation", "status": "pending"},
  {"name": "code_review", "status": "pending"},
  {"name": "delivery", "status": "pending"}
]
```

---

## 阶段三：需求采集 (requirement_intake)

### 3.1 源解析
由于输入是 `inline_text`，直接使用消息内容作为需求源，无需额外拉取。

### 3.2 LLM 需求分析
调用 `build_requirement_artifact()` ([intake/analyzer.py](file:///d:/lark/devflow/intake/analyzer.py))：

**System Prompt**：ProductRequirementAnalyst 角色提示
**User Prompt**：用户原始文本 + 结构化要求

**LLM 输出示例**（`requirement.json`）：
```json
{
  "schema_version": "devflow.requirement.v1",
  "metadata": {
    "agent": "ProductRequirementAnalyst",
    "agent_version": "0.1.0",
    "created_at": "2026-05-04T12:30:00Z"
  },
  "normalized_requirement": {
    "title": "贪吃蛇 HTML 网页单机游戏",
    "background": ["用户需要一个可在浏览器中直接运行的贪吃蛇游戏"],
    "target_users": ["普通网页用户"],
    "problem": ["缺少一个简单易玩的单机网页游戏"],
    "goals": ["实现完整的贪吃蛇游戏逻辑", "提供友好的用户界面", "支持键盘控制"],
    "non_goals": ["不实现多人对战", "不实现排行榜服务器", "不实现移动端触屏"],
    "scope": ["单个 HTML 文件", "Canvas 渲染", "本地存储最高分"]
  },
  "product_analysis": {
    "user_scenarios": ["用户在浏览器打开页面即可游玩", "使用方向键控制蛇移动"],
    "business_value": ["提供娱乐体验", "展示前端开发能力"],
    "evidence": [],
    "assumptions": ["用户浏览器支持 HTML5 Canvas", "用户有键盘"],
    "risks": ["游戏性能在低端设备可能不佳"],
    "dependencies": []
  },
  "acceptance_criteria": [
    {"id": "AC-001", "source": "llm", "criterion": "游戏区域显示在 Canvas 中，蛇身和食物清晰可见"},
    {"id": "AC-002", "source": "llm", "criterion": "使用方向键控制蛇的移动方向"},
    {"id": "AC-003", "source": "llm", "criterion": "蛇吃到食物后身体增长，得分增加"},
    {"id": "AC-004", "source": "llm", "criterion": "蛇撞墙或撞到自己时游戏结束"},
    {"id": "AC-005", "source": "llm", "criterion": "游戏结束后显示最终得分和重新开始按钮"},
    {"id": "AC-006", "source": "llm", "criterion": "最高分使用 localStorage 持久化存储"}
  ],
  "open_questions": [
    {"field": "difficulty", "question": "是否需要多难度级别（速度递增）？"},
    {"field": "ui_style", "question": "是否有特定的视觉风格要求（颜色、主题）？"}
  ],
  "quality": {
    "completeness_score": 0.85,
    "ambiguity_score": 0.15,
    "ready_for_next_stage": true,
    "warnings": ["缺少具体的视觉设计规范", "未明确是否支持移动端"]
  }
}
```

### 3.3 PRD 发布
- 调用 `create_prd_document()` 创建飞书云文档
- 发送交互式卡片到飞书会话

**requirement_intake 阶段完成状态**：
```json
{"name": "requirement_intake", "status": "success", "artifact": "artifacts/runs/.../requirement.json"}
```

---

## 阶段四：方案设计 (solution_design)

### 4.1 Workspace 解析
**关键问题**：用户消息中没有包含 `仓库：...` 或 `新项目：...` 指令。

**解析逻辑** ([solution/workspace.py:65-87](file:///d:/lark/devflow/solution/workspace.py#L65-L87))：

```python
def resolve_workspace(message_text=...):
    directive = parse_workspace_directive("创建一个贪吃蛇小游戏 html 网页单机游戏")
    # → 返回 None（没有仓库/新项目指令）
    
    # 检查 workspace.default_repo
    # 如果 config.workspace.default_repo 为空 → 抛出 WorkspaceError
```

**结果**：`WorkspaceError: 缺少仓库上下文：请提供 --repo、--new-project、机器人消息中的"仓库：..."或 workspace.default_repo。`

### 4.2 阻塞处理
由于缺少 workspace 上下文，方案设计阶段被**阻塞** ([pipeline.py:366-398](file:///d:/lark/devflow/pipeline.py#L366-L398))：

```python
# 设置 stage 状态
{"name": "solution_design", "status": "blocked", "error": "缺少仓库上下文..."}

# 创建 checkpoint.json
{
  "schema_version": "devflow.checkpoint.v1",
  "run_id": "20260504T123000Z-om_evt-xxxxxxxx",
  "stage": "solution_design",
  "status": "blocked",
  "blocked_reason": "缺少仓库上下文：请提供...",
  "continue_requested": false
}
```

### 4.3 Bot 回复（阻塞状态）
```
DevFlow 已完成需求分析，但技术方案已暂停：缺少仓库上下文：请提供 --repo、--new-project、
机器人消息中的"仓库：..."或 workspace.default_repo。 请只回复一行继续：
仓库：D:\path\to\repo 或 新项目：snake-game。
技术方案需要读取本机可访问的代码库上下文。
运行 ID：20260504T123000Z-om_evt-xxxxxxxx
需求产物：artifacts/runs/.../requirement.json
只回复一行即可继续，请复制其中一种格式：
仓库：D:\path\to\repo
新项目：snake-game
如果这是全新的网页、小游戏或工具，优先回复 `新项目：snake-game` 这类项目名。
收到后我会继续生成技术方案和评审卡片。
```

**此时 run.json 状态**：
```json
{
  "status": "blocked",
  "stages": [
    {"name": "requirement_intake", "status": "success", ...},
    {"name": "solution_design", "status": "blocked", "error": "缺少仓库上下文..."},
    {"name": "code_generation", "status": "pending"},
    ...
  ],
  "checkpoint_status": "blocked",
  "checkpoint_blocked_reason": "缺少仓库上下文..."
}
```

---

## 阶段五：用户补充 Workspace 上下文

**用户回复**：
```
新项目：snake-game
```

### 5.1 检查点恢复检测
`maybe_process_checkpoint_event()` ([pipeline.py:609-651](file:///d:/lark/devflow/pipeline.py#L609-L651))：

```python
# 1. 不是 Approve/Reject 命令
# 2. 不是等待 reject reason 的状态
# 3. 是 workspace resume 回复 → 匹配到 blocked run
blocked_run_dir = find_blocked_workspace_run(out_dir, event_source)
# → 返回之前阻塞的运行目录
```

### 5.2 恢复方案设计
`resume_blocked_solution_design()` ([pipeline.py:654-729](file:///d:/lark/devflow/pipeline.py#L654-L729))：

**Workspace 解析**：
```python
workspace = resolve_workspace(message_text="新项目：snake-game", config=config.workspace)
# → 创建目录 workspace.root/snake-game/
# → 执行 git init
# → 返回 workspace payload
{
  "mode": "new_project",
  "path": "D:\\workspace\\snake-game",
  "project_name": "snake-game",
  "repo_url": "",
  "base_branch": "main",
  "writable": true
}
```

### 5.3 代码库上下文构建
`build_codebase_context()` ([solution/workspace.py:90-141](file:///d:/lark/devflow/solution/workspace.py#L90-L141))：

由于是新建项目，目录为空：
```json
{
  "root": "D:\\workspace\\snake-game",
  "file_count": 0,
  "included_file_count": 0,
  "context_character_count": 0,
  "tree": [],
  "files": []
}
```

### 5.4 LLM 方案设计
调用 `build_solution_design_artifact()` ([solution/designer.py:92-173](file:///d:/lark/devflow/solution/designer.py#L92-L173))：

**System Prompt**：SolutionDesignArchitect 角色 ([solution/prompt.py](file:///d:/lark/devflow/solution/prompt.py))

**LLM 输出示例**（`solution.json`）：
```json
{
  "schema_version": "devflow.solution_design.v1",
  "metadata": {
    "agent": "SolutionDesignArchitect",
    "agent_version": "0.1.0",
    "created_at": "2026-05-04T12:35:00Z",
    "model": "deepseek-chat",
    "llm_provider": "deepseek"
  },
  "workspace": {
    "mode": "new_project",
    "path": "D:\\workspace\\snake-game",
    "project_name": "snake-game",
    "writable": true
  },
  "requirement_summary": {
    "title": "贪吃蛇 HTML 网页单机游戏",
    "goals": ["实现完整的贪吃蛇游戏逻辑", "提供友好的用户界面", "支持键盘控制"],
    "scope": ["单个 HTML 文件", "Canvas 渲染", "本地存储最高分"],
    "acceptance_criteria": [...],
    "ready_for_next_stage": true
  },
  "codebase_context": {
    "root": "D:\\workspace\\snake-game",
    "file_count": 0,
    "included_file_count": 0
  },
  "architecture_analysis": {
    "current_architecture": ["新建项目，无现有代码"],
    "related_modules": [],
    "constraints": ["单 HTML 文件实现", "纯前端，无后端依赖"],
    "reusable_patterns": []
  },
  "proposed_solution": {
    "summary": "使用单个 HTML 文件实现贪吃蛇游戏，包含 Canvas 渲染、游戏逻辑、键盘控制和本地存储。",
    "data_flow": ["用户按键 → 方向控制 → 游戏循环 → Canvas 渲染 → 碰撞检测 → 得分更新"],
    "implementation_steps": [
      "创建 index.html 结构",
      "实现 Canvas 游戏画布",
      "实现蛇的数据结构和移动逻辑",
      "实现食物生成和吃食物检测",
      "实现碰撞检测（墙壁和自身）",
      "实现游戏循环和渲染",
      "实现键盘事件监听",
      "实现得分和最高分存储"
    ]
  },
  "change_plan": [
    {"path": "index.html", "action": "add", "responsibility": "完整的贪吃蛇游戏实现"}
  ],
  "api_design": {
    "cli": [],
    "python": [],
    "json_contracts": [],
    "external": []
  },
  "testing_strategy": {
    "unit_tests": ["手动测试键盘控制响应", "手动测试碰撞检测"],
    "integration_tests": ["完整游戏流程测试"],
    "acceptance_mapping": ["AC-001 到 AC-006"],
    "regression_tests": []
  },
  "risks_and_assumptions": {
    "risks": ["单文件可能导致代码较长", "Canvas 性能在低端设备可能受限"],
    "assumptions": ["用户浏览器支持 HTML5", "用户有键盘输入设备"],
    "open_questions": ["是否需要响应式布局支持移动端？"]
  },
  "human_review": {
    "status": "pending",
    "checklist": [
      "确认单文件实现方案可接受",
      "确认游戏难度（速度）设定",
      "确认视觉风格（颜色方案）"
    ]
  },
  "quality": {
    "completeness_score": 0.88,
    "risk_level": "low",
    "ready_for_code_generation": true,
    "warnings": ["缺少视觉设计规范，将使用默认配色"]
  }
}
```

### 5.5 生成 solution.md
渲染人类可读的技术方案文档。

### 5.6 创建检查点
```json
{
  "schema_version": "devflow.checkpoint.v1",
  "run_id": "20260504T123000Z-om_evt-xxxxxxxx",
  "stage": "solution_design",
  "status": "waiting_approval",
  "attempt": 1,
  "reviewer": null,
  "decision": null,
  "continue_requested": false,
  "artifact_history": [{
    "attempt": 1,
    "solution_path": "artifacts/runs/.../solution.json",
    "solution_markdown_path": "artifacts/runs/.../solution.md"
  }]
}
```

### 5.7 发送评审卡片
Bot 发送交互式卡片到飞书：

```
┌─────────────────────────────────────┐
│  📝 DevFlow 技术方案评审              │
├─────────────────────────────────────┤
│  方案摘要：使用单个 HTML 文件实现...   │
│                                     │
│  运行 ID：20260504T123000Z-...      │
│  风险等级：low                      │
│                                     │
│  文件变更预览：                      │
│  • `index.html`：完整的贪吃蛇游戏实现 │
│                                     │
│  同意：Approve 20260504T123000Z-... │
│  拒绝：Reject 20260504T123000Z-...  │
└─────────────────────────────────────┘
```

**solution_design 阶段完成状态**：
```json
{"name": "solution_design", "status": "success", "artifact": "artifacts/runs/.../solution.json"}
```

---

## 阶段六：人工审批 (checkpoint)

**用户回复**：
```
Approve 20260504T123000Z-om_evt-xxxxxxxx
```

### 6.1 检查点命令解析
`parse_checkpoint_command()` ([checkpoint.py:24-38](file:///d:/lark/devflow/checkpoint.py#L24-L38))：

```python
# 匹配 "Approve {run_id}"
verb = "approve"
run_id = "20260504T123000Z-om_evt-xxxxxxxx"
→ CheckpointCommand(decision="approve", run_id="...", reason=None)
```

### 6.2 执行审批
`approve_checkpoint_run()` ([pipeline.py:732-769](file:///d:/lark/devflow/pipeline.py#L732-L769))：

```python
checkpoint = apply_checkpoint_decision(run_dir, "approve", reviewer={...})
# checkpoint.status → "approved"
# checkpoint.continue_requested → true
```

### 6.3 自动触发代码生成
```python
code_path = run_code_generation_after_approval(run_dir, run_payload)
# → 立即执行代码生成阶段！
```

---

## 阶段七：代码生成 (code_generation)

### 7.1 加载方案
```python
solution = load_solution_artifact("artifacts/runs/.../solution.json")
# 验证 schema_version、workspace.path、ready_for_code_generation
```

### 7.2 CodeGenerationAgent 工具循环
`build_code_generation_artifact()` ([code/agent.py:19-87](file:///d:/lark/devflow/code/agent.py#L19-L87))：

**初始化**：
```python
executor = CodeToolExecutor("D:\workspace\snake-game")
messages = [{"role": "system", "content": CODE_GENERATION_SYSTEM_PROMPT}]
```

**Turn 1 - LLM 请求**：
```json
{
  "solution": {
    "workspace": {"path": "D:\\workspace\\snake-game", ...},
    "requirement_summary": {"title": "贪吃蛇 HTML 网页单机游戏", ...},
    "proposed_solution": {"summary": "使用单个 HTML 文件...", ...},
    "change_plan": [{"path": "index.html", "action": "add", ...}]
  },
  "tool_events": [],
  "instruction": "根据方案继续下一步。需要文件内容时先 read_file 或 grep_search；完成后返回 finish。"
}
```

**Turn 1 - LLM 响应**（工具调用）：
```json
{"action": "tool", "tool": "write_file", "input": {
  "path": "index.html",
  "content": "<!DOCTYPE html>\n<html>...（完整贪吃蛇游戏代码）..."
}}
```

**执行工具**：
```python
executor.execute("write_file", {"path": "index.html", "content": "..."})
# → 创建 D:\workspace\snake-game\index.html
# → 记录事件到 tool_events
```

**Turn 2 - LLM 请求**（包含 tool_result）：
```json
{
  "tool_events": [{
    "tool": "write_file",
    "input": {"path": "index.html", ...},
    "status": "success",
    "result": {"status": "success", "path": "index.html", "operation": "create", "patch": "..."}
  }],
  "instruction": "..."
}
```

**Turn 2 - LLM 响应**（完成）：
```json
{"action": "finish", "summary": "已创建完整的贪吃蛇游戏页面", "changed_files": ["index.html"], "warnings": []}
```

### 7.3 生成产物

**code-generation.json**：
```json
{
  "schema_version": "devflow.code_generation.v1",
  "metadata": {
    "agent": "CodeGenerationAgent",
    "agent_version": "0.1.0",
    "created_at": "2026-05-04T12:40:00Z",
    "model": "deepseek-chat",
    "llm_provider": "deepseek"
  },
  "status": "success",
  "workspace": {
    "mode": "new_project",
    "path": "D:\\workspace\\snake-game",
    "project_name": "snake-game"
  },
  "solution_summary": {
    "title": "贪吃蛇 HTML 网页单机游戏",
    "summary": "使用单个 HTML 文件实现贪吃蛇游戏..."
  },
  "changed_files": ["index.html"],
  "summary": "已创建完整的贪吃蛇游戏页面",
  "warnings": [],
  "tool_events": [
    {
      "tool": "write_file",
      "input": {"path": "index.html", "content": "..."},
      "status": "success",
      "result": {"status": "success", "path": "index.html", "operation": "create"}
    }
  ],
  "diff": "diff --git a/index.html b/index.html\nnew file mode 100644\n...",
  "prompt": {
    "system_prompt": "你是 DevFlow 的 CodeGenerationAgent...",
    "turn_count": 2
  }
}
```

**code.diff**：
```diff
diff --git a/index.html b/index.html
new file mode 100644
index 0000000..abcd123
--- /dev/null
+++ b/index.html
@@ -0,0 +1,200 @@
+<!DOCTYPE html>
+<html lang="zh-CN">
+<head>
+    <meta charset="UTF-8">
+    <title>贪吃蛇游戏</title>
+    <style>
+        body { ... }
+    </style>
+</head>
+<body>
+    <canvas id="gameCanvas" width="400" height="400"></canvas>
+    <div>得分: <span id="score">0</span></div>
+    <div>最高分: <span id="highScore">0</span></div>
+    <button id="restartBtn">重新开始</button>
+    <script>
+        // 游戏逻辑...
+    </script>
+</body>
+</html>
```

### 7.4 Bot 回复
```
已确认技术方案并完成代码生成：20260504T123000Z-om_evt-xxxxxxxx。
产物：artifacts/runs/.../code-generation.json
```

**code_generation 阶段完成状态**：
```json
{"name": "code_generation", "status": "success", "artifact": "artifacts/runs/.../code-generation.json"}
```

---

## 最终运行状态

**run.json**：
```json
{
  "schema_version": "devflow.pipeline_run.v1",
  "run_id": "20260504T123000Z-om_evt-xxxxxxxx",
  "status": "success",
  "stages": [
    {"name": "requirement_intake", "status": "success", "started_at": "...", "ended_at": "...", "artifact": ".../requirement.json"},
    {"name": "solution_design", "status": "success", "started_at": "...", "ended_at": "...", "artifact": ".../solution.json"},
    {"name": "code_generation", "status": "success", "started_at": "...", "ended_at": "...", "artifact": ".../code-generation.json"},
    {"name": "test_generation", "status": "pending"},
    {"name": "code_review", "status": "pending"},
    {"name": "delivery", "status": "pending"}
  ],
  "requirement_artifact": "artifacts/runs/.../requirement.json",
  "solution_artifact": "artifacts/runs/.../solution.json",
  "solution_markdown": "artifacts/runs/.../solution.md",
  "code_generation_artifact": "artifacts/runs/.../code-generation.json",
  "code_diff": "artifacts/runs/.../code.diff",
  "checkpoint_status": "approved",
  "checkpoint_artifact": "artifacts/runs/.../checkpoint.json"
}
```

---

## 产物文件树

```
artifacts/runs/20260504T123000Z-om_evt-xxxxxxxx/
├── run.json                          # 流水线运行记录
├── requirement.json                  # 需求分析产物 (devflow.requirement.v1)
├── solution.json                     # 技术方案产物 (devflow.solution_design.v1)
├── solution.md                       # 人类可读技术方案
├── checkpoint.json                   # 检查点记录 (devflow.checkpoint.v1)
├── code-generation.json              # 代码生成产物 (devflow.code_generation.v1)
├── code.diff                         # Git diff 格式变更
├── trace.jsonl                       # 审计追踪日志
├── llm-request.json                  # 需求分析 LLM 请求
├── llm-response.json                 # 需求分析 LLM 响应
├── solution-llm-request.json         # 方案设计 LLM 请求
└── solution-llm-response.json        # 方案设计 LLM 响应
```

**工作区文件**：
```
D:\workspace\snake-game/
├── .git/                             # Git 仓库
└── index.html                        # 生成的贪吃蛇游戏
```

---

## 流程总结图

```
用户输入: "创建一个贪吃蛇小游戏 html 网页单机游戏"
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  1. 输入检测 (detect_requirement_input)                       │
│     → kind: inline_text                                       │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  2. 需求采集 (requirement_intake) ← running                   │
│     → LLM 分析 → requirement.json                             │
│     → 创建 PRD 文档 + 发送预览卡片                             │
│     → stage: success                                          │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  3. 方案设计 (solution_design) ← blocked!                     │
│     → 缺少 workspace 上下文                                    │
│     → 创建 checkpoint.json (blocked)                          │
│     → Bot 回复：请提供仓库路径或新项目名                         │
└──────────────────────────────────────────────────────────────┘
    │
    ▼ 用户回复: "新项目：snake-game"
┌──────────────────────────────────────────────────────────────┐
│  4. 恢复方案设计 (resume_blocked_solution_design)              │
│     → 创建 D:\workspace\snake-game\                           │
│     → git init                                                │
│     → LLM 生成方案 → solution.json + solution.md              │
│     → checkpoint.json (waiting_approval)                      │
│     → 发送评审卡片                                             │
│     → stage: success                                          │
└──────────────────────────────────────────────────────────────┘
    │
    ▼ 用户回复: "Approve 20260504T123000Z-..."
┌──────────────────────────────────────────────────────────────┐
│  5. 检查点审批 (checkpoint)                                   │
│     → checkpoint.json (approved)                              │
│     → 自动触发代码生成！                                        │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  6. 代码生成 (code_generation) ← running                      │
│     → CodeGenerationAgent 工具循环                             │
│     → write_file: index.html (完整贪吃蛇游戏)                  │
│     → finish: 返回完成状态                                     │
│     → code-generation.json + code.diff                        │
│     → stage: success                                          │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
Bot 回复: "已确认技术方案并完成代码生成..."
    │
    ▼
用户可以在 D:\workspace\snake-game\index.html 打开游戏
```

---

## 关键设计要点

1. **阻塞而非失败**：缺少 workspace 时，流程进入 `blocked` 状态而非失败，允许用户后续补充上下文继续。

2. **检查点驱动**：`checkpoint.json` 是人工审批的核心契约，记录审批状态、决策、理由和历史。

3. **自动触发代码生成**：`Approve` 命令不仅记录审批，还**立即执行** `code_generation` 阶段，无需额外命令。

4. **工具循环模式**：CodeGenerationAgent 通过 `tool`/`finish` action 与工作区交互，确保变更可审计。

5. **产物完整性**：每个阶段都有独立的 JSON 产物，形成完整的可追溯链路。
