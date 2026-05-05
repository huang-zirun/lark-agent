# 计划：新增小米 MiMo 模型 Provider 支持

## 调研结论

### MiMo API 兼容性

小米 MiMo 开放平台 API **完全兼容 OpenAI Chat Completions 格式**：

| 项目 | 值 |
|------|-----|
| API 端点 | `https://api.xiaomimimo.com/v1/chat/completions` |
| Base URL | `https://api.xiaomimimo.com/v1` |
| 认证方式 | `Authorization: Bearer <api_key>` |
| 请求格式 | OpenAI 标准（model, messages, temperature, max_tokens） |
| 响应格式 | OpenAI 标准（choices[0].message.content, usage） |
| 可用模型 | `mimo-v2-pro`、`mimo-v2-flash`、`mimo-v2-omni` |

### 现有架构分析

项目采用**极简 Provider 注册机制**：

1. [devflow/llm.py](file:///d:/lark/devflow/llm.py#L15-L20) 中 `PROVIDER_BASE_URLS` 字典注册 Provider 名称 → Base URL 映射
2. [devflow/llm.py](file:///d:/lark/devflow/llm.py#L53-L61) 中 `resolve_base_url()` 根据配置解析 Base URL
3. [devflow/llm.py](file:///d:/lark/devflow/llm.py#L79-L152) 中 `chat_completion()` 构建标准 OpenAI 兼容请求并解析响应
4. 所有 Provider 共享同一套请求/响应逻辑，前提是兼容 OpenAI 格式

**结论：MiMo 完全兼容，无需修改 `chat_completion()` 核心逻辑，只需在 `PROVIDER_BASE_URLS` 中新增一行。**

## 实施步骤

### 步骤 1：在 `PROVIDER_BASE_URLS` 中添加 MiMo Provider

**文件**：[devflow/llm.py](file:///d:/lark/devflow/llm.py#L15-L20)

在字典中新增一行：

```python
PROVIDER_BASE_URLS = {
    "ark": "https://ark.cn-beijing.volces.com/api/v3",
    "bailian": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "deepseek": "https://api.deepseek.com",
    "mimo": "https://api.xiaomimimo.com/v1",
    "openai": "https://api.openai.com/v1",
}
```

> 注意：按字母序排列，`mimo` 插入在 `deepseek` 和 `openai` 之间。

### 步骤 2：更新 `config.example.json` 中的 provider 说明

**文件**：[config.example.json](file:///d:/lark/config.example.json#L3)

将 `"provider": "ark"` 保持不变（默认值不改），但用户可配置为 `"mimo"`。

### 步骤 3：添加 MiMo Provider 的单元测试

**文件**：[tests/test_llm.py](file:///d:/lark/tests/test_llm.py#L40-L56)

在 `test_provider_default_base_urls` 测试方法中新增一个断言：

```python
self.assertEqual(
    resolve_base_url(LlmConfig(provider="mimo")),
    "https://api.xiaomimimo.com/v1",
)
```

### 步骤 4：更新 `journey/design.md` 中的 Provider 列表

**文件**：[journey/design.md](file:///d:/lark/journey/design.md)

将 Key Decisions 中的 Provider 列表从 `ark, bailian, deepseek, openai, custom` 更新为 `ark, bailian, deepseek, mimo, openai, custom`。

### 步骤 5：运行测试验证

执行 `uv run python -m pytest tests/test_llm.py -v` 确保所有测试通过。

## 变更范围

| 文件 | 变更类型 | 变更量 |
|------|---------|--------|
| `devflow/llm.py` | 新增 1 行 | 1 行 |
| `tests/test_llm.py` | 新增 3 行 | 3 行 |
| `journey/design.md` | 修改 1 行 | 1 行 |

总计：**3 个文件，约 5 行变更**，零新依赖，零架构改动。

## 风险评估

- **兼容性风险**：低。MiMo 官方明确声明兼容 OpenAI API 格式，多个第三方验证文章确认。
- **回归风险**：极低。仅新增字典条目，不修改任何现有逻辑。
- **配置风险**：无。用户需主动将 `provider` 设为 `mimo` 才会触发新路径。
