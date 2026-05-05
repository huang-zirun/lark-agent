# 修复计划：LLM JSON 解析多余尾部字符

## 根本原因

**LLM 返回的 JSON 末尾有多余的 `}` 字符**。

### 证据

Turn 2 的 LLM 响应（`code-llm-response-turn2.json`）：
- content 长度：806 字符
- 有效 JSON 结束位置：第 805 字符
- 多余字符：`}`（1个）

```
...自定义界面配色与尺寸"}}}   ← LLM 返回（3个}，多1个）
...自定义界面配色与尺寸"}}    ← 正确应该（2个}）
```

Turn 1 的 LLM 响应正常（5585 字符，无多余字符）。

### 为什么 `parse_llm_json` 无法处理

当前 `parse_llm_json` 的容错逻辑：
1. `json.loads(text)` → 失败（Extra data）
2. `text.find("{")` + `text.rfind("}")` → 提取 `{...}` 子串
3. `json.loads(substring)` → **仍然失败**（因为 `rfind("}")` 找到的是最外层的多余 `}`）

**问题**：`rfind("}")` 找到的是最后一个 `}`，而不是 JSON 对象的匹配闭合 `}`。

### 修复方案

使用 `json.JSONDecoder.raw_decode()` 替代 `json.loads()`。

`raw_decode()` 只解析第一个完整的 JSON 值，忽略后续内容。这是 Python 标准库内置的方法，无需额外依赖。

```python
decoder = json.JSONDecoder()
parsed, end_idx = decoder.raw_decode(text)
# 自动忽略 text[end_idx:] 的多余内容
```

验证结果：
- Turn 1（正常）：`raw_decode` 解析 5585 字符，无多余内容 ✅
- Turn 2（异常）：`raw_decode` 解析 805 字符，忽略 1 个多余 `}` ✅

## 修改文件

### `devflow/llm.py` - `parse_llm_json()`

```python
def parse_llm_json(text: str) -> dict[str, Any]:
    original_text = text
    text = text.strip()

    # 去除 Markdown 代码块标记
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # 使用 raw_decode 解析第一个完整 JSON 值，忽略尾部多余内容
    decoder = json.JSONDecoder()
    try:
        parsed, _ = decoder.raw_decode(text)
    except json.JSONDecodeError:
        # 如果从开头解析失败，尝试查找第一个 { 再解析
        start = text.find("{")
        if start < 0:
            raise LlmError(
                f"LLM 响应不是有效 JSON。原始响应前200字符：{original_text[:200]}"
            )
        try:
            parsed, _ = decoder.raw_decode(text, start)
        except json.JSONDecodeError as exc:
            raise LlmError(
                f"LLM 响应不是有效 JSON。原始响应前200字符：{original_text[:200]}"
            ) from exc

    if not isinstance(parsed, dict):
        raise LlmError(
            f"LLM 响应 JSON 必须是 object，实际是 {type(parsed).__name__}。"
        )
    return parsed
```

## 验证步骤

1. 单元测试 `parse_llm_json` 处理多余尾部字符
2. 运行 `tests.test_code_generation` 和 `tests.test_pipeline_start`
3. 重新运行 `uv run -m devflow start` 端到端验证
