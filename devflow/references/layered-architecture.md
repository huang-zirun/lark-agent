---
name: layered-architecture
title: 分层架构模式
description: 基于 Fowler PEAA 和 Evans DDD 的分层架构设计模式
tags: [architecture, ddd, layering]
version: "1.0"
applicable_stages: [solution_design]
priority: 6
---

## 概述

分层架构（Layered Architecture）是企业应用最广泛的结构模式，其核心原则是关注点分离（Separation of Concerns）。本参考综合 Martin Fowler《Patterns of Enterprise Application Architecture》、Eric Evans《Domain-Driven Design》及 Robert C. Martin《Clean Architecture》的思想，定义三层架构的标准结构与依赖规则。

## 三层结构

### Presentation Layer（表现层）

职责：接收用户输入、渲染输出、处理 HTTP 请求/响应。

包含：Controller、ViewModel、DTO、路由配置、中间件（认证/限流等横切关注点）。

约束：不包含业务逻辑，仅做参数校验与格式转换；通过接口调用 Business Layer。

### Business/Domain Layer（业务/领域层）

职责：封装核心业务规则与领域逻辑，是系统的心脏。

包含：Entity、Value Object、Domain Service、Application Service、Domain Event、Repository Interface。

约束：不依赖任何基础设施实现；通过接口（Port）定义对外部资源的访问需求；领域模型使用统一语言（Ubiquitous Language）。

### Data/Persistence Layer（数据/持久化层）

职责：实现 Repository 接口，管理数据存取与外部服务集成。

包含：Repository Implementation、ORM Mapping、Cache Client、Message Publisher、External API Client。

约束：仅实现 Domain Layer 定义的接口，不包含业务逻辑；技术选型变更只影响本层。

## 依赖规则

```
Presentation → Business/Domain ← Data/Persistence
```

- 依赖方向始终从外层指向内层
- Domain Layer 零外部依赖（纯逻辑层）
- 外层通过接口（Port）与内层通信
- 内层不感知外层的存在

## Port-Adapter 模式

Hexagonal Architecture（六边形架构）是分层架构的进阶形式：

- **Port**: Domain Layer 定义的接口，描述"我需要什么"
- **Adapter**: Infrastructure Layer 的实现，描述"我如何提供"
- **Driving Adapter**: 主动调用 Domain 的外部触发器（Controller、CLI、Consumer）
- **Driven Adapter**: 被 Domain 调用的外部资源（Repository、Gateway）

## 目录结构示例

```
src/
├── presentation/        # 表现层
│   ├── controller/
│   ├── dto/
│   └── middleware/
├── domain/              # 领域层（纯逻辑，零外部依赖）
│   ├── entity/
│   ├── valueobject/
│   ├── service/
│   ├── event/
│   └── port/            # Repository 接口等
└── infrastructure/      # 基础设施层
    ├── persistence/     # Repository 实现
    ├── cache/
    ├── messaging/
    └── gateway/         # 外部 API 客户端
```

## Agent 使用指引

1. **层次违规检测**: 扫描代码依赖关系，检测是否存在 Domain 层直接引用 Infrastructure 实现的情况，标注违规并建议修复。
2. **新项目结构生成**: 为新项目生成符合分层架构的目录结构与骨架代码，包含 Port 接口定义。
3. **重构建议**: 对单体代码提出分层拆分方案，识别应属于 Domain 的逻辑被错误放置在 Controller 或 Repository 中的情况。
4. **依赖方向验证**: 检查 import 语句，确保依赖方向符合规则，生成依赖关系图供评审。
