# server.py 实现计划

## 目标
创建一个统一的启动脚本 `server.py`，用于同时启动前端和后端服务。

## 项目现状分析

### 后端 (Backend)
- **框架**: FastAPI
- **入口文件**: `backend/app/main.py`
- **启动方式**: `uv run uvicorn app.main:app --reload --port 8000`
- **依赖管理**: `uv` (Python包管理器)
- **工作目录**: `backend/`

### 前端 (Frontend)
- **框架**: React + Vite
- **入口文件**: `frontend/src/main.tsx`
- **启动方式**: `npm run dev` (默认端口 5173)
- **依赖管理**: `npm`
- **工作目录**: `frontend/`

## 实现方案

### 方案选择: Python 多进程启动器
使用 Python 的 `subprocess` 和 `multiprocessing` 模块创建启动脚本，原因：
1. 与后端技术栈一致（Python）
2. 跨平台兼容性好（Windows/Linux/macOS）
3. 易于处理进程管理和信号
4. 可以统一配置和管理

### 功能需求
1. **并行启动**: 同时启动前端和后端服务
2. **端口配置**: 支持自定义前后端端口
3. **环境检测**: 自动检测依赖是否安装
4. **进程管理**: 支持优雅关闭（Ctrl+C 同时终止所有进程）
5. **日志输出**: 区分前后端日志输出
6. **健康检查**: 可选的服务健康检查

### 实现步骤

1. **创建 server.py 文件**
   - 位置: 项目根目录 `d:\进阶指南\lark-agent\server.py`
   - 使用 `subprocess.Popen` 启动两个服务
   - 使用 `signal` 处理优雅关闭

2. **参数配置**
   - `--backend-port`: 后端端口（默认 8000）
   - `--frontend-port`: 前端端口（默认 5173）
   - `--backend-host`: 后端主机（默认 127.0.0.1）
   - `--frontend-host`: 前端主机（默认 127.0.0.1）
   - `--no-backend`: 只启动前端
   - `--no-frontend`: 只启动后端

3. **依赖检查**
   - 检查 `uv` 是否安装
   - 检查 `npm` 是否安装
   - 检查前端依赖是否已安装（node_modules）

4. **进程管理**
   - 捕获 SIGINT (Ctrl+C) 信号
   - 优雅终止所有子进程
   - 确保端口释放

5. **日志输出**
   - 使用不同颜色区分前后端日志
   - 添加时间戳
   - 支持日志级别控制

## 文件结构

```
d:\进阶指南\lark-agent\
├── server.py          # 主启动脚本
├── backend/
│   └── app/
│       └── main.py    # FastAPI 入口
├── frontend/
│   ├── package.json   # npm 配置
│   └── ...
└── ...
```

## 使用方法

```bash
# 启动前后端（默认配置）
python server.py

# 指定端口
python server.py --backend-port 8080 --frontend-port 3000

# 只启动后端
python server.py --no-frontend

# 只启动前端
python server.py --no-backend
```

## 预期输出

```
[SERVER] 正在启动 DevFlow Engine...
[SERVER] 后端: http://127.0.0.1:8000
[SERVER] 前端: http://127.0.0.1:5173
[BACKEND] INFO:     Started server process [12345]
[BACKEND] INFO:     Waiting for application startup.
[BACKEND] INFO:     Application startup complete.
[FRONTEND] > devflow-engine-frontend@0.1.0 dev
[FRONTEND] > vite
[FRONTEND] 
[FRONTEND]   VITE v5.4.0  ready in 500 ms
[FRONTEND] 
[FRONTEND]   ➜  Local:   http://127.0.0.1:5173/
[SERVER] 所有服务已启动，按 Ctrl+C 停止
```

## 注意事项

1. **Windows 兼容性**: 使用 PowerShell 兼容的命令格式
2. **路径处理**: 正确处理包含空格的中文路径
3. **编码**: 使用 UTF-8 编码处理输出
4. **uv 优先**: 使用 `uv run` 启动后端，符合项目规范
