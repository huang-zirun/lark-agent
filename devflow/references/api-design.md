---
name: api-design
title: REST API 设计指南
description: 基于 RFC 9110 和 Zalando API Guidelines 的 RESTful API 设计规范
tags: [api, rest, design]
version: "1.0"
applicable_stages: [solution_design]
priority: 5
---

## 概述

本指南基于 RFC 9110 (HTTP Semantics)、OpenAPI 3.1 规范及 Zalando RESTful API Guidelines，定义 REST API 的设计规范，确保 API 一致性、可预测性与可演进性。

## URL 设计

- 使用名词复数表示资源集合：`/orders`、`/users`
- 嵌套资源表达从属关系：`/users/{id}/orders`
- URL 使用 kebab-case：`/user-profiles`
- 查询参数使用 camelCase：`?sortBy=createdAt`
- URL 末尾不加斜杠：`/orders` 而非 `/orders/`
- 避免在 URL 中编码行为：用 HTTP Method 表达动作

## HTTP 方法

| 方法 | 语义 | 幂等 | 安全 |
|---|---|---|---|
| GET | 获取资源 | 是 | 是 |
| POST | 创建资源/触发操作 | 否 | 否 |
| PUT | 全量替换 | 是 | 否 |
| PATCH | 部分更新 | 否 | 否 |
| DELETE | 删除资源 | 是 | 否 |

- POST 返回 201 Created + Location Header
- PUT/PATCH/DELETE 成功返回 200 OK 或 204 No Content
- 幂等操作可安全重试，非幂等操作需提供幂等键（Idempotency-Key Header）

## 状态码

- **200 OK**: 成功（GET/PUT/PATCH/DELETE）
- **201 Created**: 资源创建成功（POST）
- **204 No Content**: 成功无返回体（DELETE）
- **400 Bad Request**: 请求格式错误
- **401 Unauthorized**: 未认证
- **403 Forbidden**: 无权限
- **404 Not Found**: 资源不存在
- **409 Conflict**: 状态冲突
- **422 Unprocessable Entity**: 语义校验失败
- **429 Too Many Requests**: 限流
- **500 Internal Server Error**: 服务端异常

## 分页

使用 Cursor-Based Pagination 优先，Offset-Based 作为兼容方案：

```
GET /orders?cursor=eyJpZCI6MTAwfQ&limit=20
```

响应包含：`items`、`nextCursor`、`hasMore`。

## 过滤与排序

- 过滤：`?status=active&createdAt.gte=2024-01-01`
- 排序：`?sort=-createdAt,updatedAt`（`-` 表示降序）
- 字段选择：`?fields=id,name,status`

## 版本控制

- 优先使用 URL 前缀：`/v1/orders`
- 版本号仅在大版本（Breaking Change）时递增
- 向后兼容的变更（新增字段、新增端点）不升级版本

## 限流

- 响应 Header 包含：`X-RateLimit-Limit`、`X-RateLimit-Remaining`、`X-RateLimit-Reset`
- 超限返回 429 + `Retry-After` Header

## Agent 使用指引

1. **API 骨架生成**: 根据资源定义自动生成 OpenAPI 3.1 规范骨架与 Controller 代码框架。
2. **设计一致性检查**: 检查已有 API 是否符合本指南规范（URL 命名、状态码使用、分页方式等）。
3. **Breaking Change 检测**: 对比 API 变更前后，识别 Breaking Change 并提示版本升级。
4. **文档生成**: 基于 OpenAPI 规范自动生成 API 文档摘要。
