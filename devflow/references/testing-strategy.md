---
name: testing-strategy
title: 测试策略与覆盖率目标
description: 基于 Fowler 测试金字塔和 ISTQB 的测试策略与覆盖率标准
tags: [testing, coverage, strategy]
version: "1.0"
applicable_stages: [test_generation]
priority: 10
---

## 概述

测试策略决定质量保障的投入产出比。本参考基于 Martin Fowler 测试金字塔、ISTQB 测试分级标准及 Google Testing Blog 推荐实践，定义测试分层比例、覆盖率目标与测试策略文档结构。

## 测试金字塔

```
        /  E2E  \           10% — 少量，高成本，高价值
       /Integration\        20% — 适度，验证模块协作
      /    Unit      \      70% — 大量，低成本，快速反馈
```

### Unit Test（单元测试）

- **范围**: 单个函数/方法/类，隔离外部依赖
- **速度**: ≤ 10ms/用例
- **隔离**: 使用 Mock/Stub 替代数据库、网络、文件系统
- **命名**: `should_{expected}_when_{condition}`
- **结构**: Given-When-Then（Arrange-Act-Assert）
- **原则**: 测试行为而非实现，不测私有方法，不过度 Mock

### Integration Test（集成测试）

- **范围**: 模块间协作、数据库交互、API 调用
- **速度**: ≤ 1s/用例
- **策略**: 使用真实数据库（Testcontainers）或内存数据库；验证 SQL 正确性、事务行为、序列化/反序列化
- **重点**: Repository 层、Service 层跨模块调用、消息队列交互

### E2E Test（端到端测试）

- **范围**: 完整用户旅程，从 UI 到数据库
- **速度**: 秒级~分钟级
- **策略**: 仅覆盖核心业务流程（Happy Path + 关键异常路径）；使用独立的测试环境与数据
- **工具**: Playwright / Cypress / Pact（Contract Testing 替代部分 E2E）

## 覆盖率目标

| 指标 | 最低要求 | 推荐目标 | 说明 |
|---|---|---|---|
| Line Coverage | ≥ 80% | ≥ 90% | 语句覆盖 |
| Branch Coverage | ≥ 70% | ≥ 80% | 分支覆盖 |
| Function Coverage | ≥ 90% | 100% | 函数入口覆盖 |
| Critical Path | 100% | 100% | 支付/认证/数据写入等关键路径 |

覆盖率是必要条件而非充分条件：高覆盖率不等于高质量，需结合变异测试（Mutation Testing）评估测试有效性。

## 测试分类标签

| 标签 | 含义 | 运行时机 |
|---|---|---|
| @unit | 单元测试 | 每次提交 |
| @integration | 集成测试 | 每次提交 |
| @e2e | 端到端测试 | 合并至主分支 |
| @smoke | 冒烟测试 | 部署后 |
| @slow | 慢速测试（>1s） | CI 夜间任务 |

## 测试策略文档结构

1. **测试目标**: 质量目标与风险容忍度
2. **测试范围**: 被测系统边界与排除项
3. **测试分层**: 各层比例与工具选型
4. **覆盖率要求**: 按模块设定差异化目标
5. **测试数据策略**: 数据生成、隔离与清理
6. **CI 集成**: 测试执行时机与失败处理
7. **缺陷分析**: 缺陷分类与根因分析流程

## Agent 使用指引

1. **测试骨架生成**: 根据函数签名与逻辑分支，自动生成单元测试骨架，覆盖 Given-When-Then 结构与边界条件。
2. **覆盖率缺口分析**: 分析现有测试覆盖率报告，识别未覆盖的分支与关键路径，按优先级排序。
3. **测试分类**: 自动识别测试类型（Unit/Integration/E2E），建议添加分类标签。
4. **测试质量审查**: 检测测试中的反模式（过度 Mock、测试实现细节、缺少断言、测试间依赖），输出改进建议。
