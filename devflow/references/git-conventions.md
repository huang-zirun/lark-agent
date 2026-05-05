---
name: git-conventions
title: Git 分支与提交约定
description: 基于 Conventional Commits 和 SemVer 的 Git 工作流规范
tags: [git, commit, branching]
version: "1.0"
applicable_stages: [code_generation]
priority: 5
---

## 概述

统一的 Git 约定是团队协作的基础。本参考基于 Conventional Commits 1.0 规范与 Semantic Versioning 2.0 标准，定义分支策略、提交消息格式与版本管理规则。

## 分支策略

### GitHub Flow（推荐）

适用于持续部署场景，流程简洁：

1. `main` 分支始终可部署
2. 从 `main` 创建功能分支：`feat/{ticket}-{description}`
3. 完成后提交 Pull Request
4. Code Review 通过后合并至 `main`
5. 合并即触发部署

### Git Flow

适用于有明确发布周期的项目：

- `main`: 生产代码
- `develop`: 开发集成分支
- `feature/*`: 功能分支
- `release/*`: 发布准备分支
- `hotfix/*`: 紧急修复分支

### Trunk-Based Development

适用于高成熟度团队：

- 所有人在 `main`（Trunk）上频繁提交
- 使用 Feature Flag 控制未完成功能
- 短生命周期分支（≤1 天）

## 提交消息格式

```
<type>(<scope>): <subject>

[body]

[footer]
```

### Type 枚举

| Type | 含义 | SemVer 影响 |
|---|---|---|
| feat | 新功能 | MINOR |
| fix | Bug 修复 | PATCH |
| docs | 文档变更 | - |
| style | 格式调整（不影响逻辑） | - |
| refactor | 重构（非新功能/非修复） | - |
| perf | 性能优化 | PATCH |
| test | 测试相关 | - |
| build | 构建系统或依赖 | - |
| ci | CI 配置变更 | - |
| chore | 其他杂项 | - |

### Scope

可选，表示影响范围：模块名、组件名或包名。如 `feat(auth): add OAuth2 PKCE support`。

### Subject

- 使用祈使句（"add" 而非 "added"）
- 首字母小写，末尾不加句号
- 长度 ≤ 72 字符

### Breaking Change

在 Footer 中标记：

```
BREAKING CHANGE: auth API now requires Bearer token instead of API key
```

或在 Type 后加 `!`：`feat(auth)!: migrate from API key to Bearer token`

Breaking Change 对应 SemVer MAJOR 版本递增。

## 分支命名规范

| 类型 | 格式 | 示例 |
|---|---|---|
| 功能 | `feat/{ticket}-{desc}` | `feat/PROJ-123-oauth-pkce` |
| 修复 | `fix/{ticket}-{desc}` | `fix/PROJ-456-login-timeout` |
| 热修复 | `hotfix/{ticket}-{desc}` | `hotfix/PROJ-789-payment-failure` |
| 发布 | `release/v{version}` | `release/v2.1.0` |

## Agent 使用指引

1. **提交消息生成**: 分析代码 diff，自动生成符合 Conventional Commits 格式的提交消息，识别 type 与 scope。
2. **分支命名**: 创建分支时自动按规范命名，关联 Ticket 编号。
3. **变更日志生成**: 基于提交历史，按 type 分组生成 CHANGELOG，标注 Breaking Change。
4. **规范检查**: 检查提交消息是否符合格式要求，标注不符合规范的提交。
