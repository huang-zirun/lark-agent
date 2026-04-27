# 修复 OpenAI API 401 认证错误

## 问题描述

在网页执行 DevFlow Engine 任务时，Stage `requirement_analysis` 执行失败，错误信息为：

```
Stage requirement_analysis failed: Stage requirement_analysis execution failed: Agent requirement_agent execution failed: OpenAI API authentication failed: 401
```

## 当前环境配置

`.env` 文件已存在，配置了火山引擎（Volces）API：

```env
OPENAI_API_KEY=ark-68e0d61c-2646-4a0e-8ac1-7ea35da99d21-a6c8f
OPENAI_API_BASE=https://ark.cn-beijing.volces.com/api/v3
OPENAI_DEFAULT_MODEL=ep-20260423222610-xbx2l
```

## 根本原因分析

### 1. 数据库 Provider 配置与 .env 不同步

`.env` 文件虽然配置正确，但数据库中的 `provider_config` 表可能存储了：
- 旧的/错误的 API 密钥
- 不同的 API Base URL
- 或者根本没有 Provider 记录

`fix_provider.py` 脚本只在 `OPENAI_API_KEY` 存在且数据库中没有 OpenAI Provider 时才会创建。如果之前已经创建了错误的记录，脚本不会更新它。

### 2. API 密钥加密/解密问题

`.env` 文件中的 `ENCRYPTION_KEY` 已更改为 `your-encryption-key-32-bytes-long`，但之前数据库中的 API 密钥可能是用旧的加密密钥加密的。这会导致解密失败，返回错误的 API 密钥。

查看 `provider_registry.py` 中的解密逻辑：
```python
def _decrypt_api_key(encrypted: str | None) -> str:
    if not encrypted:
        return ""
    try:
        # ... 解密逻辑
    except Exception:
        return encrypted  # 解密失败时返回原始加密字符串！
```

如果解密失败，会返回原始加密字符串，而不是正确的 API 密钥。

### 3. 火山引擎 API 认证方式差异

火山引擎的 OpenAI 兼容 API 可能需要特定的认证头格式，与标准 OpenAI API 略有不同。

## 修复方案

### 方案 1: 同步数据库 Provider 配置（推荐）

删除数据库中旧的 Provider 记录，让 `fix_provider.py` 根据当前 `.env` 重新创建。

**步骤：**
1. 停止后端服务
2. 备份并删除数据库文件，或删除 provider_config 表中的记录
3. 运行 `fix_provider.py` 重新创建 Provider
4. 启动后端服务
5. 验证 Provider 配置

### 方案 2: 直接更新数据库中的 Provider

通过 API 直接更新现有 Provider 的配置。

**步骤：**
1. 查询现有 Provider ID
2. 调用 PUT /api/providers/{id} 更新 API 密钥
3. 验证 Provider 配置

### 方案 3: 修复加密密钥问题

如果问题是加密密钥变更导致的，需要：
1. 恢复原来的 `ENCRYPTION_KEY`，或
2. 删除数据库中的 Provider 记录，使用新的加密密钥重新创建

## 实施计划

### 步骤 1: 诊断当前状态

检查数据库中 Provider 的实际配置：
- 查询 provider_config 表中的记录
- 检查 api_key_encrypted 字段
- 验证 api_base 是否正确

### 步骤 2: 清理并重建 Provider 配置

选择以下方式之一：

**方式 A - 重置数据库（彻底）：**
```powershell
cd E:\系统文件夹\Desktop\Channing\lark-agent
# 备份数据库
Copy-Item data\devflow.db data\devflow.db.backup
# 删除数据库（会丢失所有数据）
Remove-Item data\devflow.db
# 重新初始化
```

**方式 B - 仅删除 Provider 记录（推荐）：**
通过 SQLite 工具或 API 删除 provider_config 表中的记录，然后运行 `fix_provider.py`

### 步骤 3: 验证修复

1. 运行 `uv run python tests/test_api_key.py` 验证 API 密钥
2. 调用 `/api/providers/{id}/validate` 验证 Provider
3. 重新执行 Pipeline 测试

## 代码改进（可选）

### 1. 增强错误信息

修改 `openai_compatible.py` 第 56-57 行：
```python
if response.status_code == 401 or response.status_code == 403:
    error_detail = response.text[:500] if response.text else "No details"
    raise AuthenticationError(
        f"OpenAI API authentication failed: {response.status_code}. "
        f"Details: {error_detail}. "
        f"Please check your API key and API base configuration."
    )
```

### 2. 添加 Provider 配置预检

在 `provider_registry.py` 的 `_create_provider_from_config` 函数中添加：
```python
api_key = _decrypt_api_key(config.api_key_encrypted) if config.api_key_encrypted else ""
if not api_key:
    raise ExecutionError(
        f"Provider {config.id} ({config.name}) has no valid API key. "
        f"The API key may be empty or decryption failed."
    )
```

### 3. 改进 fix_provider.py

添加更新现有 Provider 的功能，而不仅仅是创建新的。

## 验证清单

- [ ] 数据库中的 Provider 记录与 `.env` 配置一致
- [ ] `uv run python tests/test_api_key.py` 测试通过
- [ ] `/api/providers/{id}/validate` 返回 `valid: true`
- [ ] 重新执行 Pipeline，`requirement_analysis` 阶段成功
