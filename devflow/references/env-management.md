---
name: env-management
title: 环境与配置管理策略
description: 基于 12-Factor App 和 HashiCorp Vault 的环境配置管理规范
tags: [environment, configuration, secrets]
version: "1.0"
applicable_stages: [code_generation]
priority: 4
---

## 概述

环境与配置管理是应用交付的基础保障。本参考基于 12-Factor App 第三因子（Config）与 HashiCorp Vault 最佳实践，定义环境分层、配置管理与密钥管理的标准策略。

## 环境分层

| 环境 | 用途 | 数据 | 部署方式 |
|---|---|---|---|
| Local | 开发者本地调试 | Mock/Seed | 手动启动 |
| CI | 自动化测试 | 测试数据 | Pipeline 自动 |
| Staging | 预发布验证 | 生产镜像数据 | 合并至 develop 自动 |
| Production | 正式服务 | 真实数据 | 手动审批触发 |
| Canary | 灰度验证 | 真实流量子集 | 渐进式滚动 |

环境间配置必须隔离，禁止跨环境共享密钥与数据库。

## 配置管理

### 12-Factor 第三因子

> 将配置存储在环境变量中，而非代码中。

配置指随部署环境变化的值（数据库连接串、API 地址、功能开关），不包括业务逻辑中的常量。

### 配置分层模型

按优先级从高到低：

1. **环境变量**: 容器/运行时注入，最高优先级
2. **环境专属配置文件**: `.env.staging`、`.env.production`
3. **默认配置文件**: `.env`、`config/default.yaml`
4. **代码内默认值**: 硬编码的合理默认值

优先级高的覆盖低的，确保环境变量可覆盖一切。

### 配置项命名规范

- 使用 `UPPER_SNAKE_CASE`
- 按模块前缀分组：`DB_HOST`、`REDIS_URL`、`AUTH_JWT_SECRET`
- 布尔值使用 `ENABLE_X` 或 `DISABLE_X`，避免双重否定

### 配置验证

应用启动时必须校验必填配置项：

- 缺少必填项：启动失败并输出明确错误信息
- 类型不匹配：启动失败并提示期望类型
- 值越界：启动失败或输出警告

## 密钥管理

### 存储原则

- 禁止将密钥提交至代码仓库（使用 .gitignore 排除 .env 文件）
- 禁止在日志中输出密钥值
- 禁止在 URL 参数中传递密钥

### 密钥轮换

- 定期轮换（建议 ≤ 90 天）
- 支持双密钥过渡期（新旧密钥同时有效）
- 轮换操作自动化，避免人工介入

### 密钥管理工具

| 场景 | 推荐方案 |
|---|---|
| 云原生 | AWS Secrets Manager / GCP Secret Manager |
| 自托管 | HashiCorp Vault |
| 开发本地 | .env + dotenv（仅 Local 环境） |
| CI/CD | Pipeline 内置密钥管理 |

### 密钥注入方式

- 容器：通过 Kubernetes Secrets / Docker Secrets 挂载为环境变量
- 应用：启动时从 Vault 拉取，缓存于内存，不落盘
- CI：通过 Pipeline 变量注入，构建日志脱敏

## Agent 使用指引

1. **配置模板生成**: 根据技术栈生成配置模板文件（.env.example、config/default.yaml），包含所有必需配置项及注释说明。
2. **硬编码密钥检测**: 扫描代码，检测硬编码的密钥、Token、密码，标注风险等级并建议迁移至环境变量。
3. **环境一致性检查**: 对比不同环境的配置项，检测缺失或冲突的配置。
4. **密钥轮换提醒**: 识别长期未轮换的密钥，输出轮换建议。
