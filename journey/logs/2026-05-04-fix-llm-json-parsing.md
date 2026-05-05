# 修复 LLM JSON 解析失败问题

## 问题描述

在飞书机器人输入需求后，代码生成阶段出现 `LLM 响应不是有效 JSON` 错误，导致流程中断。

## 根本原因（经审计日志确认）

### 第一轮分析（初步）

1. **模型返回格式不一致**：使用的 `doubao-seed-2-0-pro-260215` 模型（火山引擎方舟平台）有时会返回被 Markdown 代码块包裹的 JSON，或在 JSON 前后添加推理说明
2. **`parse_llm_json` 容错能力不足**：原实现只能处理纯 JSON 或简单包含 `{}` 的文本
3. **代码生成阶段缺乏审计**：没有保存 LLM 原始响应，难以排查问题

### 第二轮分析（审计日志确认，2026-05-04）

通过代码生成阶段新增的审计日志 `code-llm-response-turn{N}.json`，**确认了真正的根本原因**：

**LLM 返回的嵌套 JSON 末尾多了一个 `}`**。

```
...自定义界面配色与尺寸"}}}   ← LLM 返回（3个}，多1个）
...自定义界面配色与尺寸"}}    ← 正确应该（2个}）
```

验证方法：
```python
decoder = json.JSONDecoder()
parsed, end_idx = decoder.raw_decode(content)
# end_idx=805, len(content)=806
# content[805] = '}'  ← 多余的闭合大括号
```

**为什么 `rfind("}")` 方案无法修复**：`rfind("}")` 找到的是最后一个 `}`，恰好是多余的。提取 `{...}` 子串后仍包含多余的 `}`，`json.loads` 依然报 `Extra data`。

## 修复内容

### 1. 增强 `parse_llm_json` 容错能力 ([devflow/llm.py](file:///d:/lark/devflow/llm.py#L164-L197))

**第一轮修复**：
- 自动去除 Markdown 代码块标记（```json ... ```）
- 错误信息包含原始响应前200字符，便于调试
- 类型错误提示更明确（显示实际类型）

**第二轮修复（关键）**：
- 使用 `json.JSONDecoder.raw_decode()` 替代 `json.loads()`
- `raw_decode()` 只解析第一个完整 JSON 值，自动忽略尾部多余内容
- 这是 Python 标准库内置方法，无需额外依赖

```python
decoder = json.JSONDecoder()
parsed, _ = decoder.raw_decode(text)  # 自动忽略尾部多余字符
```

### 2. 代码生成阶段添加审计日志 ([devflow/code/agent.py](file:///d:/lark/devflow/code/agent.py#L42))

- 每轮 LLM 调用后保存 `code-llm-response-turn{N}.json`
- 包含完整的 LLM 响应内容、token 使用、耗时等信息
- **这个审计日志是定位根本原因的关键**——没有它就无法看到 LLM 实际返回了什么

### 3. 验证 `response_format_json` 支持

- 火山引擎方舟平台支持 `response_format: {"type": "json_object"}`（Beta 阶段）
- 当前代码已支持该配置（[llm.py:92-93]）
- 可在 `config.json` 中设置 `"response_format_json": true` 启用
- **建议暂不启用**，观察 `raw_decode` 修复效果后再决定

## 验证结果

### 单元测试
- `tests.test_code_generation`: 5/5 通过
- `tests.test_pipeline_start`: 20/20 通过

### 手动验证
- 正常 JSON ✅
- 末尾多余 `}` ✅（核心修复点）
- 前缀文本 + JSON + 后缀文本 ✅
- Markdown 代码块 ✅
- 无 JSON（报错）✅
- JSON 数组（报错）✅
- **真实 Turn 2 响应** ✅

## 后续建议

1. 重新运行 `uv run -m devflow start` 端到端验证完整流程
2. 如仍有问题，启用 `config.json` 中的 `"response_format_json": true`
3. 考虑为所有 LLM 调用阶段统一添加审计日志保存机制
