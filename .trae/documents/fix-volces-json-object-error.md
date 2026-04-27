# 修复火山引擎 API 400 错误 - json_object 不支持

## 问题描述

Stage `requirement_analysis` 执行失败，错误信息：

```
OpenAI API error: 400 - {"error":{"code":"InvalidParameter","message":"The parameter `response_format.type` specified in the request are not valid: `json_object` is not supported by this model."
```

## 根本原因

火山引擎（Volces）的某些模型不支持 OpenAI 的 `response_format: {"type": "json_object"}` 参数。

在 `openai_compatible.py` 第 41 行：
```python
if use_structured_output:
    schema_prompt = f"..."
    messages[-1]["content"] = messages[-1]["content"] + schema_prompt
    payload["response_format"] = {"type": "json_object"}  # <-- 这行导致错误
```

## 修复方案

### 方案 1: 移除 response_format 参数（推荐）

对于火山引擎等 OpenAI 兼容 API，不使用 `response_format` 参数，仅通过 prompt 要求返回 JSON。代码已经通过 `schema_prompt` 在提示词中要求模型返回 JSON，所以移除 `response_format` 参数后仍然可以正常工作。

修改 `openai_compatible.py` 第 41 行：
```python
# 移除或注释掉这行
# payload["response_format"] = {"type": "json_object"}
```

### 方案 2: 根据 API Base 动态决定是否使用 response_format

检测 API Base 是否包含火山引擎域名，如果是则不使用 `response_format`：

```python
if use_structured_output:
    schema_prompt = f"..."
    messages[-1]["content"] = messages[-1]["content"] + schema_prompt
    # 火山引擎不支持 json_object
    if "volces.com" not in self.api_base:
        payload["response_format"] = {"type": "json_object"}
```

### 方案 3: 捕获 400 错误并自动重试

当收到 400 错误且包含 `json_object` 不支持的信息时，自动重试请求（不包含 `response_format` 参数）。

## 实施计划

采用**方案 1**（最简单直接）：

1. 修改 `openai_compatible.py`，移除 `response_format` 参数
2. 保留 `schema_prompt` 通过提示词要求返回 JSON
3. 验证修复

## 代码修改

文件：`backend/app/core/provider/openai_compatible.py`

修改前（第 37-41 行）：
```python
use_structured_output = schema is not None
if use_structured_output:
    schema_prompt = f"\n\n请严格按照以下 JSON Schema 格式返回结果：\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n只返回 JSON，不要包含其他内容。"
    messages[-1]["content"] = messages[-1]["content"] + schema_prompt
    payload["response_format"] = {"type": "json_object"}
```

修改后：
```python
use_structured_output = schema is not None
if use_structured_output:
    schema_prompt = f"\n\n请严格按照以下 JSON Schema 格式返回结果：\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n只返回 JSON，不要包含其他内容。"
    messages[-1]["content"] = messages[-1]["content"] + schema_prompt
    # 注意：某些 OpenAI 兼容 API（如火山引擎）不支持 response_format 参数
    # 仅通过 prompt 要求返回 JSON 即可
```

## 验证步骤

1. 修改代码后重启后端服务
2. 重新执行 Pipeline
3. 确认 `requirement_analysis` 阶段成功
