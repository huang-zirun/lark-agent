# 统一启动脚本实施记录

**日期**: 2026-05-05  
**任务**: 将前端、后端、Bot 监控脚本合并为一个启动脚本，实现一键启动

## 背景

项目包含三个需要同时运行的服务：
- **后端 API**: `uv run devflow serve` (端口 8080)
- **Bot 事件监听**: `uv run devflow start` (长驻进程)
- **前端 Dashboard**: `npm run dev --prefix dashboard` (端口 5173)

此前需要开三个终端分别启动，体验差且容易遗漏。

## 方案调研

对比了 5 种业界主流方案：

| 方案 | Windows 兼容性 | 日志区分 | 优雅退出 | 复杂度 | 结论 |
|------|--------------|---------|---------|--------|------|
| **concurrently** | ✅ 优秀 | ✅ 彩色前缀 | ✅ Ctrl+C 全杀 | 低 | **选中** |
| Honcho (Procfile) | ⚠️ 一般 | ✅ 前缀标签 | ⚠️ 信号传播弱 | 低 | 备选 |
| docker-compose | ⚠️ 需 Docker Desktop | ✅ 分容器日志 | ✅ 容器停止 | 高 | 生产/CI 适用 |
| PM2 | ⚠️ 需 WSL | ✅ 文件轮转 | ✅ 守护重启 | 中 | 生产部署适用 |
| npm-run-all | ✅ 优秀 | ❌ 无前缀着色 | ✅ Ctrl+C | 低 | 项目已归档 |

**选择 concurrently 的理由**:
1. Windows 兼容性最好（纯 Node.js，无信号传播问题）
2. 零配置上手，与现有 package.json 无缝集成
3. 彩色前缀日志，一眼区分三个服务输出
4. `--kill-others-on-fail` 支持任一进程崩溃时全部退出
5. npm 周下载量 800 万+，社区成熟稳定

## 实施步骤

### 1. 安装 concurrently

```bash
npm install -D concurrently
```

### 2. 修改根 package.json

添加统一启动脚本和子命令：

```json
{
  "scripts": {
    "dev": "concurrently -n api,bot,dashboard -c blue,green,magenta --kill-others-on-fail \"uv run devflow serve\" \"uv run devflow start\" \"npm run dev --prefix dashboard\"",
    "dev:api": "uv run devflow serve",
    "dev:bot": "uv run devflow start",
    "dev:dashboard": "npm run dev --prefix dashboard"
  }
}
```

### 3. 创建 Procfile 服务声明文档

```
api:       uv run devflow serve
bot:       uv run devflow start
dashboard: npm run dev --prefix dashboard
```

Procfile 作为服务声明文档，方便团队成员了解需要哪些服务，也可供 Honcho 用户直接使用。

## 验证结果

运行 `npm run dev` 成功启动三个服务：

```
[dashboard] VITE v8.0.10  ready in 581 ms
[dashboard] ➜  Local:   http://localhost:5173/dashboard/
```

- ✅ Dashboard 成功启动在 5173 端口
- ✅ 三个进程同时运行无崩溃
- ✅ 日志带颜色前缀 `[api]` `[bot]` `[dashboard]`
- ✅ Ctrl+C 可优雅退出所有进程

## 最终效果

```bash
# 一键启动全部服务
npm run dev

# 单独启动某个服务
npm run dev:api
npm run dev:bot
npm run dev:dashboard
```

## 涉及文件

| 文件 | 操作 |
|------|------|
| `package.json` | 修改：添加 concurrently 依赖和 dev 脚本 |
| `Procfile` | 新建：服务声明文档 |

## 相关文档

- 详细计划: `.trae/documents/unified-startup-script-plan.md`
