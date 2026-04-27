# 修复 Vite 代理 ECONNREFUSED ::1:19999 错误

## 问题定位

Terminal 报错：
```
[vite] http proxy error: /api/pipelines
Error: connect ECONNREFUSED ::1:19999
```

Vite 前端代理尝试将 `/api/pipelines` 请求转发到后端，但连接被拒绝。

## 根因分析

### 原因 1（主要）：IPv6 优先解析导致连接失败

- [vite.config.ts](file:///e:/系统文件夹/Desktop/Channing/lark-agent/frontend/vite.config.ts#L10) 代理目标为 `http://localhost:19999`
- Node.js 18+ 中 `dns.lookup('localhost')` 优先返回 IPv6 地址 `::1`
- [run.py](file:///e:/系统文件夹/Desktop/Channing/lark-agent/backend/run.py#L10) 中 uvicorn 绑定 `host="0.0.0.0"`，仅监听 IPv4
- 结果：Vite 代理尝试连接 `::1:19999`（IPv6），后端只在 `0.0.0.0:19999`（IPv4）上监听 → ECONNREFUSED

### 原因 2（次要）：server.py 默认端口与前端代理不一致

- [server.py](file:///e:/系统文件夹/Desktop/Channing/lark-agent/server.py#L374) 默认后端端口为 `8000`
- [config.py](file:///e:/系统文件夹/Desktop/Channing/lark-agent/backend/app/shared/config.py#L12) 默认后端端口为 `19999`
- [vite.config.ts](file:///e:/系统文件夹/Desktop/Channing/lark-agent/frontend/vite.config.ts#L10) 代理指向 `19999`
- 如果通过 `python server.py` 启动（不带参数），后端监听 8000，前端代理请求 19999 → ECONNREFUSED

### 原因 3（可能）：后端未启动

后端进程可能未运行，任何端口配置下都会 ECONNREFUSED。

## 修复步骤

### 步骤 1：修复 Vite 代理 IPv6 问题

**文件**: `frontend/vite.config.ts`

将 `target` 从 `http://localhost:19999` 改为 `http://127.0.0.1:19999`，强制使用 IPv4 地址，绕过 Node.js 的 IPv6 优先解析。

```typescript
proxy: {
  '/api': {
    target: 'http://127.0.0.1:19999',
    changeOrigin: true,
  },
},
```

### 步骤 2：修复 server.py 默认端口不一致

**文件**: `server.py`

将 `--backend-port` 默认值从 `8000` 改为 `19999`，与 `config.py` 和 Vite 代理保持一致。

```python
parser.add_argument(
    "--backend-port",
    type=int,
    default=19999,
    help="后端服务端口 (默认: 19999)",
)
```

同时将 `--frontend-port` 默认值从 `5173` 改为 `3000`，与 `vite.config.ts` 中 `server.port: 3000` 保持一致。

```python
parser.add_argument(
    "--frontend-port",
    type=int,
    default=3000,
    help="前端服务端口 (默认: 3000)",
)
```

同步修改 `ServerManager.__init__` 的默认参数：

```python
def __init__(
    self,
    backend_port: int = 19999,
    frontend_port: int = 3000,
    ...
):
```

### 步骤 3：验证修复

1. 确保后端已启动（在 `backend/` 目录下执行 `uv run python run.py`）
2. 重启前端开发服务器
3. 确认 `/api/pipelines` 请求不再报 ECONNREFUSED

## 影响范围

| 文件 | 修改内容 | 风险 |
|------|---------|------|
| `frontend/vite.config.ts` | `localhost` → `127.0.0.1` | 极低，仅影响开发代理 |
| `server.py` | 默认端口 8000→19999, 5173→3000 | 低，仅影响默认值，显式传参不受影响 |
