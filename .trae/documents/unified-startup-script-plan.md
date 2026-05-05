# 统一启动脚本实施计划

## 背景

当前项目包含三个需要同时运行的服务：

| 服务 | 启动命令 | 端口/说明 |
|------|---------|-----------|
| 后端 API | `uv run devflow serve --host 127.0.0.1 --port 8080` | HTTP 8080 |
| Bot 事件监听 | `uv run devflow start` | 长驻进程，消费飞书 IM 事件 |
| 前端 Dashboard | `npm run dev --prefix dashboard` | Vite 开发服务器 5173 |

目前需要开三个终端分别启动，体验差且容易遗漏。

## 业界最佳实践调研

### 方案对比

| 方案 | Windows 兼容性 | 日志区分 | 优雅退出 | 环境变量 | 复杂度 | 适合场景 |
|------|--------------|---------|---------|---------|--------|---------|
| **concurrently** | ✅ 优秀 | ✅ 彩色前缀 | ✅ Ctrl+C 全杀 | 需自行处理 | 低 | 开发态首选 |
| **Honcho** (Procfile) | ⚠️ 一般 | ✅ 前缀标签 | ⚠️ 信号传播弱 | ✅ .env 自动加载 | 低 | Python 项目 |
| **docker-compose** | ⚠️ 需 Docker Desktop | ✅ 分容器日志 | ✅ 容器停止 | ✅ .env/yaml | 高 | 生产/CI |
| **PM2** | ⚠️ 需 WSL | ✅ 文件轮转 | ✅ 守护重启 | ✅ ecosystem.config | 中 | 生产部署 |
| **npm-run-all** | ✅ 优秀 | ❌ 无前缀着色 | ✅ Ctrl+C | 需自行处理 | 低 | 简单串/并行 |

### 推荐方案：concurrently

**理由**：
1. Windows 兼容性最好（纯 Node.js，无信号传播问题）
2. 零配置上手，与现有 `package.json` 无缝集成
3. 彩色前缀日志，一眼区分三个服务输出
4. `--kill-others-on-fail` 支持任一进程崩溃时全部退出
5. npm 周下载量 800 万+，社区成熟稳定
6. 项目已有根 `package.json`，添加成本极低

### 辅助方案：Procfile 作为服务声明文档

即使不用 Honcho 启动，Procfile 本身是服务清单的好文档，方便团队成员了解需要哪些服务。

## 实施步骤

### Step 1: 安装 concurrently 依赖

在根目录 `package.json` 的 `devDependencies` 中添加 `concurrently`：

```bash
npm install -D concurrently
```

### Step 2: 修改根目录 package.json，添加统一启动脚本

在根目录 `package.json` 的 `scripts` 中添加：

```json
{
  "scripts": {
    "dev": "concurrently -n api,bot,dashboard -c blue,green,magenta --kill-others-on-fail \"uv run devflow serve\" \"uv run devflow start\" \"npm run dev --prefix dashboard\"",
    "dev:api": "uv run devflow serve",
    "dev:bot": "uv run devflow start",
    "dev:dashboard": "npm run dev --prefix dashboard",
    "lark": "lark-cli",
    "lark:version": "lark-cli --version",
    "lark:auth": "lark-cli auth status"
  }
}
```

**关键参数说明**：
- `-n api,bot,dashboard`：三个进程的名称标签
- `-c blue,green,magenta`：日志颜色区分
- `--kill-others-on-fail`：任一进程异常退出时，自动终止其余进程
- 保留 `dev:api`、`dev:bot`、`dev:dashboard` 子命令，方便单独启动某个服务

### Step 3: 创建 Procfile 作为服务声明文档

在项目根目录创建 `Procfile`：

```
api:       uv run devflow serve
bot:       uv run devflow start
dashboard: npm run dev --prefix dashboard
```

这是声明式文档，方便团队成员一眼看清需要哪些服务，也可供 Honcho 用户直接 `honcho start` 使用。

### Step 4: 验证

1. 运行 `npm run dev`，确认三个服务同时启动
2. 检查日志是否带颜色前缀，可区分来源
3. 测试 Ctrl+C 是否能优雅退出所有进程
4. 测试 `npm run dev:api` 等子命令是否正常工作

## 最终效果

```bash
# 一键启动全部服务
npm run dev

# 单独启动某个服务
npm run dev:api
npm run dev:bot
npm run dev:dashboard
```

终端输出示例：

```
[api]       INFO: Starting DevFlow API server on 127.0.0.1:8080
[bot]       INFO: Listening for bot events...
[dashboard] VITE v8.0.10  ready in 300 ms
[dashboard] ➜  Local:   http://localhost:5173/
```

## 涉及文件

| 文件 | 操作 |
|------|------|
| `package.json`（根目录） | 修改：添加 concurrently 依赖和 dev 脚本 |
| `Procfile`（新建） | 新建：服务声明文档 |
