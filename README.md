# DevFlow Engine

飞书 AI 校园挑战赛参赛作品 - AI 驱动的需求交付流程引擎

## 项目概述

DevFlow Engine 是一个 AI 驱动的需求到代码交付流程引擎，通过自动化 Pipeline 将自然语言需求转换为可交付的代码变更。

## 技术栈

- **后端**: Python 3.11+, FastAPI, SQLAlchemy (async), SQLite
- **前端**: React 18, TypeScript, Vite, Ant Design
- **AI 集成**: OpenAI-compatible API, Anthropic Claude

## 快速开始

### 后端

```bash
cd backend
uv venv
uv pip install -e ".[dev]"
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000

## 核心功能

- **Pipeline 编排**: 8 阶段自动化流程（需求分析→方案设计→检查点→代码生成→测试→审查→检查点→交付）
- **检查点审批**: 支持设计审批和最终审批两个人工检查点
- **Artifact 管理**: 7 种结构化产物（需求简报、设计规范、变更集、测试报告、审查报告、交付总结）
- **Provider 注册中心**: 支持 OpenAI、Anthropic 等 LLM Provider

## API 文档

启动后端后访问 http://127.0.0.1:8000/docs

## 项目结构

```
lark-agent/
├── backend/          # FastAPI 后端
│   ├── app/
│   │   ├── api/      # REST API 路由
│   │   ├── core/     # 核心服务
│   │   ├── models/   # SQLAlchemy ORM 模型
│   │   ├── schemas/  # Pydantic 数据模型
│   │   └── agents/   # AI Agent 实现
│   └── pyproject.toml
├── frontend/         # React 前端
│   └── src/
│       ├── components/
│       └── pages/
└── docs/             # 设计文档
```
