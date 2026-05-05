# 分析计划：DevFlow test\_generation 阶段失败根因分析

## 实验概况

* **Run ID**: `20260504T024548Z-om_x100b50b4cb1c94a0b2709b68401174e-f26fdc47`

* **需求**: 创建春天风格贪吃蛇 HTML 单机小游戏

* **最终状态**: `failed`，失败阶段 `test_generation`

* **错误信息**: `old_string 和 new_string 必须不同`

***

## 失败根因分析

### 直接原因

TestGenerationAgent 的 LLM（doubao-seed-2-0-pro-260215）在调用 `edit_file` 工具时，使用了 **`find`** **和** **`replace`** 作为参数名，而不是 `edit_file` 方法所期望的 **`old_string`** **和** **`new_string`**。

具体证据来自 [test-llm-response-turn2.json](file:///d:/lark/artifacts/runs/20260504T024548Z-om_x100b50b4cb1c94a0b2709b68401174e-f26fdc47/test-llm-response-turn2.json) 中 LLM 的输出：

```json
{
  "action": "tool",
  "tool": "edit_file",
  "input": {
    "path": "D:\\lark\\workspaces\\snake-game\\test.html",
    "find": "...(游戏重启逻辑测试代码)...",
    "replace": "...(游戏重启逻辑测试代码 + 新增操作响应延迟测试)..."
  }
}
```

### 错误传播链

1. **LLM 输出** `input.find` 和 `input.replace` 字段
2. **`normalize_agent_action()`** ([agent.py:115](file:///d:/lark/devflow/test/agent.py#L115)) 将 `input` 字典原样透传，无字段名映射
3. **`executor.execute("edit_file", action["input"])`** ([agent.py:54](file:///d:/lark/devflow/test/agent.py#L54)) 调用 `CodeToolExecutor.execute()`
4. **`CodeToolExecutor.execute()`** ([tools.py:36-41](file:///d:/lark/devflow/code/tools.py#L36-L41)) 从 payload 中读取 `old_string` 和 `new_string`：

   * `payload.get("old_string")` → `None`（因为实际字段名是 `find`）

   * `payload.get("new_string")` → `None`（因为实际字段名是 `replace`）

   * `str(None or "")` → `""`（空字符串）
5. **`edit_file("", "")`** 触发校验：`old_string == new_string`（两个空字符串相等）→ 抛出 `ValueError("old_string 和 new_string 必须不同")`

### 根本原因

**系统提示词未明确指定** **`edit_file`** **工具的参数名**。

两个 Agent 的系统提示词都只写了：

```
{"action":"tool","tool":"read_file|write_file|edit_file|glob_search|grep_search|powershell","input":{...}}
```

`input:{...}` 中的具体字段名完全依赖 LLM 自行推断。LLM（doubao-seed-2-0-pro）将 `edit_file` 的参数推断为 `find`/`replace`（类似 sed 命令的语义），而代码实现期望的是 `old_string`/`new_string`（类似 Claude Code 的 SearchReplace 工具语义）。

### 次要问题

1. **workspace 路径校验阻塞**：`solution_design` 阶段出现 `仓库路径必须位于 workspace.root 内：D:\lark\workspaces` 的警告，但最终被用户 approve 通过，未造成直接失败
2. **LLM 的 edit\_file 策略低效**：LLM 想在 test.html 末尾追加一个新测试用例，却选择了 `edit_file`（需要精确匹配已有代码），而非直接 `write_file` 覆盖整个文件。而且 `find` 内容包含了整个已有测试用例（只是为了在后面追加逗号和新用例），这种操作本身就很脆弱

***

## 解决方案调研

### 方案 A：在系统提示词中明确指定工具参数签名（推荐）

**思路**：在 `CODE_GENERATION_SYSTEM_PROMPT` 和 `TEST_GENERATION_SYSTEM_PROMPT` 中，将 `input:{...}` 替换为每个工具的完整参数签名说明。

**修改位置**：

* [devflow/code/prompt.py](file:///d:/lark/devflow/code/prompt.py#L7-L16) — `CODE_GENERATION_SYSTEM_PROMPT`

* [devflow/test/prompt.py](file:///d:/lark/devflow/test/prompt.py#L7-L11) — `TEST_GENERATION_SYSTEM_PROMPT`

**修改内容示例**：

```python
CODE_GENERATION_SYSTEM_PROMPT = """你是 DevFlow 的 CodeGenerationAgent。
...
可返回两类对象：
{"action":"tool","tool":"read_file|write_file|edit_file|glob_search|grep_search|powershell","input":{...}}
{"action":"finish","summary":"...","changed_files":["relative/path"],"warnings":[]}

工具参数说明：
- read_file: {"path":"相对路径","offset":0,"limit":null}
- write_file: {"path":"相对路径","content":"文件内容"}
- edit_file: {"path":"相对路径","old_string":"待查找的原始文本","new_string":"替换后的新文本","replace_all":false}
- glob_search: {"pattern":"glob模式"}
- grep_search: {"pattern":"正则表达式","glob":"文件模式"}
- powershell: {"command":"命令","timeout_seconds":60}
"""
```

**优点**：

* 从根源消除参数名歧义，对所有 LLM 模型有效

* 不改变代码执行逻辑，风险最低

* 符合"提示词工程"最佳实践

**缺点**：

* 增加系统提示词 token 消耗（约 100-150 tokens）

* 需要维护提示词与代码实现的同步

### 方案 B：在 `normalize_agent_action()` 中添加参数名别名映射

**思路**：在 `normalize_agent_action()` 中，当 `tool == "edit_file"` 时，将 `find` 映射为 `old_string`，`replace` 映射为 `new_string`。

**修改位置**：

* [devflow/code/agent.py](file:///d:/lark/devflow/code/agent.py#L104-L119) — 代码生成 Agent 的 `normalize_agent_action()`

* [devflow/test/agent.py](file:///d:/lark/devflow/test/agent.py#L134-L149) — 测试生成 Agent 的 `normalize_agent_action()`

**修改内容示例**：

```python
def normalize_agent_action(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "").strip().lower()
    if action == "finish":
        ...
    if action == "tool":
        tool = str(payload.get("tool") or "").strip()
        tool_input = payload.get("input") if isinstance(payload.get("input"), dict) else {}
        if not tool:
            raise LlmError("...")
        # 参数名别名映射
        if tool == "edit_file":
            if "find" in tool_input and "old_string" not in tool_input:
                tool_input["old_string"] = tool_input.pop("find")
            if "replace" in tool_input and "new_string" not in tool_input:
                tool_input["new_string"] = tool_input.pop("replace")
        return {"action": "tool", "tool": tool, "input": tool_input}
    raise LlmError("...")
```

**优点**：

* 容错性强，即使 LLM 使用了非标准参数名也能正常工作

* 不增加提示词 token

**缺点**：

* 属于 ad-hoc patch，只是掩盖了提示词不完整的问题

* 需要在两个 agent 的 `normalize_agent_action()` 中都添加（代码重复）

* 未来如果 LLM 使用其他非标准参数名，仍需继续添加映射

* 不符合"拒绝 ad-hoc patch"的原则

### 方案 C：方案 A + 方案 B 组合（防御性编程）

**思路**：方案 A 作为主要修复，方案 B 作为防御性兜底。

**优点**：

* 提示词明确规范参数名（治本）

* 代码层容错（治标，防患于未然）

**缺点**：

* 两处修改，维护成本略高

***

## 推荐方案

**推荐方案 A**（在系统提示词中明确指定工具参数签名），理由：

1. **治本而非治标**：根本原因是提示词歧义，应从源头修复
2. **拒绝 ad-hoc patch**：方案 B 属于典型的 ad-hoc patch，只是绕过问题而非解决问题
3. **可维护性**：提示词中的参数签名是唯一的"契约"，代码实现是"执行者"，保持两者一致比在中间层做映射更清晰
4. **通用性**：对所有 LLM 模型有效，不依赖特定模型的参数名偏好

### 实施步骤

1. 修改 [devflow/code/prompt.py](file:///d:/lark/devflow/code/prompt.py) 的 `CODE_GENERATION_SYSTEM_PROMPT`，添加工具参数签名说明
2. 修改 [devflow/test/prompt.py](file:///d:/lark/devflow/test/prompt.py) 的 `TEST_GENERATION_SYSTEM_PROMPT`，添加同样的工具参数签名说明
3. 运行现有测试验证修改不破坏已有功能
4. （可选）考虑将工具参数签名提取为共享常量，避免两个提示词中的重复定义

