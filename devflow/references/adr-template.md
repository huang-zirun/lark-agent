---
name: adr-template
title: 架构决策记录模板
description: 基于 Nygard ADR 和 MADR 的架构决策记录标准模板
tags: [architecture, decision, documentation]
version: "1.0"
applicable_stages: [solution_design]
priority: 9
---

## 概述

架构决策记录（Architecture Decision Record, ADR）由 Michael Nygard 提出，后经 MADR (Markdown Architectural Decision Records) 社区扩展，并被 ISO/IEC/IEEE 42010 架构描述标准采纳为决策捕获的推荐实践。ADR 的核心价值在于记录"为什么这样做"而非"做了什么"，使团队理解决策上下文，避免重复讨论或盲目推翻历史决策。

## ADR 格式

### 标题

`ADR-{编号}: {简短标题}`

编号采用递增整数（如 ADR-001、ADR-002），标题应简洁表达决策主题。

### Status（状态）

| 状态值 | 含义 |
|---|---|
| Proposed | 已提议，待评审 |
| Accepted | 已批准，生效中 |
| Deprecated | 已弃用，被后续 ADR 取代 |
| Superseded | 已被 ADR-{N} 替代 |

### Context（上下文）

描述决策时的客观情况，包括：
- 业务背景与驱动力
- 技术约束（团队技能、基础设施、时间）
- 需要解决的具体问题
- 不做决策的后果

此节应保持中立，不包含倾向性表述。

### Decision（决策）

明确陈述选择了什么方案，以及选择理由。格式：

> 我们选择 {方案}，因为 {理由}。

可包含：
- 选择的方案描述
- 关键权衡（Trade-off）说明
- 与备选方案的对比结论

### Consequences（后果）

列出决策带来的所有后果，包括正面与负面：

- **正面**: 带来的收益与能力提升
- **负面**: 引入的限制、风险或技术债
- **中性**: 需要注意的副作用或依赖

### Compliance（合规验证）

描述如何验证该决策被正确执行：
- 代码层面的检查方式（Lint 规则、架构测试）
- 评审要点
- 需要持续关注的指标

## 最佳实践

1. **编号连续**: 使用递增编号，不回收，即使被 Superseded 也不删除
2. **范围明确**: 一个 ADR 只记录一个决策，避免合并多个不相关决策
3. **版本控制**: ADR 纳入代码仓库，与代码同步演进
4. **轻量优先**: 不追求完美文档，重点记录 Context 和 Decision
5. **关联引用**: 被取代的 ADR 在 Status 中注明 Superseded by ADR-{N}

## Agent 使用指引

1. **生成 ADR 草稿**: 当涉及技术选型、架构模式、框架升级等决策时，自动生成 ADR 草稿，填充 Context 与 Decision 段落。
2. **一致性检查**: 扫描已有 ADR，检测新决策是否与既有决策矛盾，若矛盾则提示需要更新 Status 为 Superseded。
3. **后果评估**: 对提议的决策，分析并列举可能的正面与负面后果，辅助团队全面评估。
4. **合规追踪**: 为每个 ADR 生成可验证的 Compliance 检查项，确保决策落地不偏离。
