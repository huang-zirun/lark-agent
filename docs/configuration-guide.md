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
lark-cli auth login --