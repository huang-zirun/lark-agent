---
name: tech-selection
title: 技术选型评估框架
description: 基于 ThoughtWorks 技术雷达和 AWS Well-Architected 的技术选型评估体系
tags: [technology, evaluation, decision]
version: "1.0"
applicable_stages: [solution_design]
priority: 7
---

## 概述

技术选型是架构设计中最具长期影响的决策之一。本框架参考 ThoughtWorks Technology Radar 的分类方法与 AWS Well-Architected Framework 的评审维度，提供结构化的评估方法与加权评分矩阵，确保选型过程客观、可追溯、可复现。

## 评估维度

### 1. Functional Fit（功能匹配度）

所选技术是否满足核心功能需求？是否存在功能缺口需要自研补齐？优先选择开箱即用覆盖度高的方案。

### 2. Maturity（成熟度）

评估标准：版本号是否 ≥ 1.0？是否有生产级案例？是否仍在积极维护？社区是否活跃（Issue 响应速度、Release 频率）？

### 3. Community（社区生态）

GitHub Stars、Stack Overflow 问答数、插件/扩展数量、贡献者规模。强社区意味着更快的 Bug 修复与更丰富的生态。

### 4. Performance（性能表现）

在目标负载下的基准测试数据：吞吐量、延迟、内存占用。需与业务 SLA 对齐，留出安全余量。

### 5. Security（安全性）

是否有已知 CVE？安全更新响应速度？是否支持审计日志、加密、权限控制？是否符合合规要求？

### 6. Learning Curve（学习曲线）

团队现有技术栈的关联度、文档质量、示例丰富度。学习曲线过陡会拖慢交付并增加风险。

### 7. Maintainability（可维护性）

代码可读性、架构清晰度、测试友好度、调试工具链。长期维护成本往往超过初始开发成本。

### 8. License（许可证）

开源协议类型（MIT/Apache 2.0/GPL/AGPL 等）是否与商业模式兼容？是否存在专利风险？

### 9. Lock-in Risk（锁定风险）

迁移成本有多高？数据格式是否开放？是否有标准化的替代方案？避免不可逆的供应商锁定。

### 10. TCO（总拥有成本）

包含许可证费、基础设施成本、运维人力、培训成本、迁移成本。3-5 年总成本对比。

## 加权评分矩阵

为每个维度赋予权重（根据项目特点调整），对候选方案逐项打分（1-5 分），计算加权总分：

| 维度 | 权重 | 方案 A | 方案 B | 方案 C |
|---|---|---|---|---|
| Functional Fit | 25% | | | |
| Maturity | 15% | | | |
| Community | 10% | | | |
| Performance | 15% | | | |
| Security | 10% | | | |
| Learning Curve | 5% | | | |
| Maintainability | 5% | | | |
| License | 5% | | | |
| Lock-in Risk | 5% | | | |
| TCO | 5% | | | |
| **加权总分** | **100%** | | | |

## 决策流程

1. 明确功能需求与约束条件
2. 筛选 2-3 个候选方案
3. 逐维度调研并打分
4. 计算加权总分，识别关键差异
5. 撰写 ADR 记录决策过程与结论

## Agent 使用指引

1. **选型建议**: 当需要引入新技术时，基于项目上下文推荐候选方案并预填充评分矩阵。
2. **调研辅助**: 对候选方案自动检索版本信息、许可证、已知 CVE、社区活跃度等客观数据。
3. **风险标注**: 对 Lock-in Risk 高、License 不兼容或 Maturity 不足的方案标注警告。
4. **决策文档化**: 将评分矩阵与结论自动写入 ADR，确保选型过程可追溯。
