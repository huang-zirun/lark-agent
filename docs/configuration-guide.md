# DevFlow Engine 完整配置指南

## 一、环境前置条件

### 1.1 Python 环境

| 项目 | 要求 |
|---|---|
| Python 版本 | ≥ 3.11 |
| 包管理器 | `uv`（优先） |
| 安装 uv | `pip install uv` |

### 1.2 Node.js 环境

| 项目 | 要求 |
|---|---|
| 用途 | lark-cli 安装 + 前端仪表板 |
| 安装 lark-cli | `npm.cmd install -g @larksuite/cli@1.0.23` |
| 安装 Skills | `npx.cmd skills add larksuite/cli -y -g` |

### 1.3 Lark CLI 安装与初始化

```powershell
# 1. 全局安装指定版本（版本锁定 1.0.23，不可更改）
npm.cmd install -g @larksuite/cli@1.0.23

# 2. 安装 Skills
npx.cmd skills add larksuite/cli -y -g

# 3. 初始化配置
lark-cli config init --new

# 4. 登录授权
lark-cli auth login
```

## 二、项目配置

### 2.1 配置文件

复制示例配置文件并进行修改：

```powershell
copy config.example.json config.json
```

### 2.2 配置项说明

编辑 `config.json` 文件，填写以下关键配置：

```json
{
  "lark": {
    "app_id": "your-app-id",
    "app_secret": "your-app-secret",
    "encrypt_key": "your-encrypt-key",
    "verification_token": "your-verification-token",
    "webhook_url": "https://your-webhook-url"
  },
  "llm": {
    "provider": "openai",
    "api_key": "your-api-key",
    "model": "gpt-4",
    "base_url": "https://api.openai.com/v1"
  },
  "pipeline": {
    "max_retries": 3,
    "timeout_seconds": 300,
    "approval_required": true
  }
}
```

### 2.3 环境变量（可选）

也可以通过环境变量覆盖配置：

```powershell
$env:LARK_APP_ID = "your-app-id"
$env:LARK_APP_SECRET = "your-app-secret"
$env:OPENAI_API_KEY = "your-api-key"
```

## 三、依赖安装

### 3.1 Python 依赖

使用 uv 安装项目依赖：

```powershell
# 创建虚拟环境
uv venv

# 激活虚拟环境
.venv\Scripts\activate

# 安装依赖
uv pip install -e .
```

### 3.2 前端依赖

```powershell
cd dashboard
npm install
```

## 四、启动服务

### 4.1 启动后端服务

```powershell
# 方式一：使用 uv 运行
uv run python -m devflow

# 方式二：使用 Python 直接运行
python -m devflow
```

### 4.2 启动前端仪表板

```powershell
cd dashboard
npm run dev
```

### 4.3 启动完整服务（推荐）

```powershell
# 使用项目提供的启动脚本
./start.ps1
```

## 五、验证安装

### 5.1 检查 Lark CLI

```powershell
lark-cli --version
# 应输出: lark-cli version 1.0.23
```

### 5.2 检查 Python 环境

```powershell
python --version
# 应输出: Python 3.11.x 或更高版本

uv --version
# 应输出 uv 版本信息
```

### 5.3 测试飞书连接

```powershell
lark-cli auth check
```

## 六、常见问题

### 6.1 Lark CLI 安装失败

- 确保 Node.js 版本 ≥ 18
- 使用管理员权限运行 PowerShell
- 检查网络连接，必要时使用代理

### 6.2 Python 依赖冲突

```powershell
# 清理并重新安装
uv pip sync uv.lock
```

### 6.3 授权失败

- 确保飞书应用已发布并启用
- 检查 app_id 和 app_secret 是否正确
- 确认应用具有所需的权限范围

### 6.4 其他
- dashboard 目录下没有 node_modules 文件夹 ，所以 vite 命令找不到：在 dashboard 目录安装依赖或者从项目根目录：npm install --prefix dashboard
- cross-env 命令未找到：npm install

## 七、相关文档

- [项目 README](../README.md)
- [API 设计文档](../devflow/references/api-design.md)
- [环境管理指南](../devflow/references/env-management.md)
- [Git 提交规范](../devflow/references/git-conventions.md)
