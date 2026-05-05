---
name: ears-syntax
title: EARS 需求语法模式
description: 基于 EARS 方法的结构化需求编写模式，消除需求歧义
tags: [requirement, syntax, standard]
version: "1.0"
applicable_stages: [requirement_intake]
priority: 10
---

## 概述

EARS (Easy Approach to Requirements Syntax) 由 Mavin 等人于 2009 年在 RE 会议提出，后被 ISO/IEC/IEEE 29148 采纳。其核心思想是为每类需求提供固定语法模板，强制作者以结构化方式表达，从而减少歧义与遗漏。EARS 定义了五种基本模式加一种复合模式，覆盖了绝大多数功能需求的表达场景。

## 五加一模式

### 1. Ubiquitous（普遍型）

**模板**: The \<system\> shall \<action\>

**适用场景**: 系统在任何条件下都必须满足的行为，无前置条件。

**示例**: The payment system shall generate a unique transaction ID for each payment.

### 2. Event-Driven（事件驱动型）

**模板**: When \<event\>, the \<system\> shall \<action\>

**适用场景**: 需求由特定事件触发，事件是瞬时发生的。

**示例**: When the user submits the order, the system shall validate the inventory and reserve the items.

### 3. Unwanted Behaviour（异常处理型）

**模板**: If \<unwanted condition\>, then the \<system\> shall \<action\>

**适用场景**: 描述系统对错误、异常或非法输入的处理方式。

**示例**: If the payment gateway returns a timeout, then the system shall retry up to 3 times with exponential backoff and log the failure.

### 4. State-Driven（状态驱动型）

**模板**: While \<state\>, the \<system\> shall \<action\>

**适用场景**: 需求在系统处于某种持续状态时始终生效。

**示例**: While the account is suspended, the system shall block all write operations and display a reactivation notice.

### 5. Optional Feature（可选特性型）

**模板**: Where \<feature\>, the \<system\> shall \<action\>

**适用场景**: 需求仅在特定配置或功能启用时生效。

**示例**: Where multi-currency support is enabled, the system shall display real-time exchange rates from the configured provider.

### 6. Complex（复合型）

**模板**: 组合上述模式，使用 When/While/If/Where 嵌套

**适用场景**: 单一基本模式无法完整表达时，组合多个前置条件。

**示例**: When the user clicks "Export" while the report is in draft state, if the dataset exceeds 10000 rows, then the system shall generate an async export task and notify the user upon completion.

## 模式选择决策

| 条件特征 | 推荐模式 |
|---|---|
| 无前置条件 | Ubiquitous |
| 瞬时触发 | Event-Driven |
| 持续状态 | State-Driven |
| 异常/错误 | Unwanted Behaviour |
| 配置/特性开关 | Optional Feature |
| 多条件组合 | Complex |

## Agent 使用指引

1. **需求规范化**: 当收到自然语言需求时，识别其条件特征并套用对应 EARS 模板，输出结构化需求语句。
2. **歧义检测**: 检查需求是否缺少触发条件（应使用 Event-Driven 却写成 Ubiquitous）、是否缺少异常处理（缺少 Unwanted Behaviour 分支）。
3. **验收标准生成**: 基于每条 EARS 需求，自动生成正向与反向验收标准（Acceptance Criteria），正向验证主流程，反向验证异常路径。
4. **完整性检查**: 对一组需求进行扫描，确认每种 EARS 模式是否覆盖了应有的场景，尤其是 Unwanted Behaviour 是否被遗漏。
