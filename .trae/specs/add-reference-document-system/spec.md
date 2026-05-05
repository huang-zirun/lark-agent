# 参考文档体系 Spec

## Why

当前 DevFlow Engine 的 Agent 在执行需求分析、方案设计、代码生成、测试生成和代码评审时，仅依赖 LLM 的通用知识和代码库上下文（`build_codebase_context`），缺乏行业规范和最佳实践的注入。竞品 orchestration-engine 通过 13 个行业规范文档（EARS、ADR、NFR 等）为 Architect 和 Reviewer Agent 提供结构化知识基座，使 Agent 输出更专业、更一致。本功能旨在以 clean room 方式实现参考文档体系，基于公开行业标准和最佳实践编写内容，按需注入到各阶段 Agent 的 prompt 中，提升方案设计和代码评审的专业性和规范性。

## What Changes

- 新增 `devflow/references/` 目录，存放 12 个行业规范参考文档（Markdown + YAML front matter 格式）
- 新增 `devflow/references/registry.py`，实现参考文档注册表（元数据索引 + 懒加载 + 按需截断 + 章节提取）
- 修改 `devflow/config.py`，新增 `ReferenceConfig` 配置节
- 修改 `config.example.json`，新增 `reference` 配置段
- 修改 5 个 Agent 的 prompt 构建逻辑，按需注入参考文档内容
- 修改 `devflow/solution/workspace.py` 的 `build_codebase_context`，在返回值中增加 `reference_documents` 字段

## Impact

- Affected specs: `devflow.solution_design.v1`（新增 `reference_documents_used` 字段）、`devflow.code_review.v1`（新增 `reference_documents_used` 字段）
- Affected code: `devflow/references/`（新增）、`devflow/config.py`、`devflow/solution/designer.py`、`devflow/solution/workspace.py`、`devflow/intake/analyzer.py`、`devflow/code/prompt.py`、`devflow/test/prompt.py`、`devflow/review/prompt.py`

## ADDED Requirements

### Requirement: Reference Document Registry

系统 SHALL 提供参考文档注册表（`ReferenceRegistry`），管理所有参考文档的元数据索引、懒加载和按需读取。

#### Scenario: 启动时构建轻量索引

- **WHEN** `ReferenceRegistry` 初始化
- **THEN** 扫描 `devflow/references/` 目录下所有 `.md` 文件，仅读取 YAML front matter（`---` 之间的内容）构建元数据索引，不加载正文内容
- **AND** 元数据索引包含：`name`（文档标识）、`title`（显示标题）、`description`（一句话描述）、`tags`（标签列表）、`version`（版本号）、`applicable_stages`（适用阶段列表）、`file_path`（文件路径）、`char_count`（正文字符数估算）

#### Scenario: 按需加载文档内容

- **WHEN** 调用 `registry.get_document(name, section=None, max_chars=2000)`
- **THEN** 首次调用时加载完整 Markdown 正文并缓存，后续调用从缓存读取
- **AND** 如果指定 `section`，仅提取该 `## ` 级别章节的内容
- **AND** 如果内容超过 `max_chars`，截断到 `max_chars` 并追加 `"\n\n... (截断，如需特定章节请指定 section 参数)"`

#### Scenario: 按阶段查询适用文档

- **WHEN** 调用 `registry.get_documents_for_stage(stage_name, max_total_chars=4000)`
- **THEN** 返回所有 `applicable_stages` 包含 `stage_name` 的文档列表
- **AND** 按文档优先级排序（YAML front matter 中的 `priority` 字段，默认 0）
- **AND** 累计字符数不超过 `max_total_chars`，超出部分跳过
- **AND** 返回格式为 `[{"name": str, "title": str, "content": str}]`

#### Scenario: 禁用参考文档

- **WHEN** `config.reference.enabled` 为 `false`
- **THEN** `ReferenceRegistry` 初始化为空注册表，所有 `get_document` / `get_documents_for_stage` 调用返回空列表

### Requirement: Reference Document Content

系统 SHALL 提供 12 个行业规范参考文档，所有内容基于公开行业标准和最佳实践编写，不引用任何私有实现。

#### Scenario: 参考文档清单

- **THEN** 系统包含以下 12 个参考文档：

| name | title | 适用阶段 | 内容来源 |
|------|-------|----------|----------|
| `ears-syntax` | EARS 需求语法模式 | requirement_intake | Mavin et al. RE 2009, ISO/IEC/IEEE 29148 |
| `nfr-checklist` | 非功能需求检查清单 | requirement_intake, code_review | ISO/IEC 25010, OWASP ASVS, Google SRE |
| `adr-template` | 架构决策记录模板 | solution_design | Nygard ADR, MADR, ISO/IEC/IEEE 42010 |
| `tech-selection` | 技术选型评估框架 | solution_design | ThoughtWorks Radar, AWS Well-Architected |
| `layered-architecture` | 分层架构模式 | solution_design | Fowler PEAA, Evans DDD, Clean Architecture |
| `api-design` | REST API 设计指南 | solution_design | RFC 9110, OpenAPI 3.1, Zalando Guidelines |
| `db-schema` | 数据库 Schema 设计原则 | solution_design | SQL Style Guide, Flyway Best Practices |
| `auth-flow` | 认证授权流程模式 | solution_design | OWASP Cheat Sheets, RFC 6749/7636/7519 |
| `git-conventions` | Git 分支与提交约定 | code_generation | Conventional Commits 1.0, SemVer 2.0 |
| `env-management` | 环境与配置管理策略 | code_generation | 12-Factor App, HashiCorp Vault |
| `testing-strategy` | 测试策略与覆盖率目标 | test_generation | Fowler Test Pyramid, ISTQB, Google Testing |
| `release-checklist` | 发布就绪检查清单 | code_review, delivery | Google SRE, Atlassian Release Mgmt |

#### Scenario: 文档格式规范

- **WHEN** 编写参考文档
- **THEN** 每个文档遵循以下格式：

```markdown
---
name: ears-syntax
title: EARS 需求语法模式
description: 结构化需求编写语法，消除自然语言歧义
tags: [requirements, syntax, validation]
version: "1.0"
applicable_stages: [requirement_intake]
priority: 10
---

## 概述
[文档正文]

## 模式列表
[按章节组织]

## Agent 使用指引
[如何在本阶段 Agent 中应用本文档]
```

- **AND** 每个文档正文控制在 1500-3000 字符
- **AND** 每个文档包含 `## Agent 使用指引` 章节，指导 Agent 如何应用该规范

### Requirement: Agent Prompt Injection

系统 SHALL 在各阶段 Agent 的 prompt 中按需注入参考文档内容。

#### Scenario: 方案设计 Agent 注入

- **WHEN** `build_solution_design_user_prompt` 被调用
- **THEN** 在 `prompt_payload` 中新增 `reference_documents` 字段
- **AND** 该字段包含 `solution_design` 阶段适用的所有参考文档（`adr-template`, `tech-selection`, `layered-architecture`, `api-design`, `db-schema`, `auth-flow`）
- **AND** 累计字符数不超过 `config.reference.max_chars_per_stage`（默认 4000）
- **AND** `SOLUTION_DESIGN_ARCHITECT_PROMPT` 中增加参考文档使用指引段落

#### Scenario: 代码生成 Agent 注入

- **WHEN** `build_code_generation_user_prompt` 被调用
- **THEN** 在 payload 中新增 `reference_documents` 字段
- **AND** 该字段包含 `code_generation` 阶段适用的参考文档（`git-conventions`, `env-management`）
- **AND** 累计字符数不超过 `config.reference.max_chars_per_stage`（默认 2000）

#### Scenario: 测试生成 Agent 注入

- **WHEN** `build_test_generation_user_prompt` 被调用
- **THEN** 在 payload 中新增 `reference_documents` 字段
- **AND** 该字段包含 `test_generation` 阶段适用的参考文档（`testing-strategy`）
- **AND** 累计字符数不超过 `config.reference.max_chars_per_stage`（默认 2000）

#### Scenario: 代码评审 Agent 注入

- **WHEN** `build_code_review_user_prompt` 被调用
- **THEN** 在 payload 中新增 `reference_documents` 字段
- **AND** 该字段包含 `code_review` 阶段适用的参考文档（`nfr-checklist`, `release-checklist`）
- **AND** 累计字符数不超过 `config.reference.max_chars_per_stage`（默认 2000）

#### Scenario: 需求分析 Agent 注入

- **WHEN** `build_llm_user_prompt` 被调用
- **THEN** 在 user prompt 的 JSON payload 中新增 `reference_documents` 字段
- **AND** 该字段包含 `requirement_intake` 阶段适用的参考文档（`ears-syntax`, `nfr-checklist`）
- **AND** 累计字符数不超过 `config.reference.max_chars_per_stage`（默认 2000）

### Requirement: Reference Configuration

系统 SHALL 在 `config.json` 中支持参考文档配置。

#### Scenario: 配置结构

- **WHEN** 用户配置参考文档系统
- **THEN** `config.json` 中新增 `reference` 配置段：

```json
{
  "reference": {
    "enabled": true,
    "max_chars_per_stage": 4000,
    "max_chars_per_document": 2000
  }
}
```

- **AND** `ReferenceConfig` 数据类包含：`enabled: bool = True`、`max_chars_per_stage: int = 4000`、`max_chars_per_document: int = 2000`

#### Scenario: 配置合并到 DevflowConfig

- **WHEN** `load_config()` 加载配置
- **THEN** `DevflowConfig` 新增 `reference: ReferenceConfig` 字段
- **AND** 缺少 `reference` 段时使用默认值

### Requirement: Artifact Traceability

系统 SHALL 在产物中记录使用了哪些参考文档，便于审计和调试。

#### Scenario: 方案设计产物记录

- **WHEN** 方案设计完成并写入 `solution.json`
- **THEN** 产物中新增 `reference_documents_used` 字段，值为 `[{"name": str, "title": str, "chars_injected": int}]`
- **AND** 该字段记录实际注入到 prompt 中的参考文档及其注入字符数

#### Scenario: 代码评审产物记录

- **WHEN** 代码评审完成并写入 `code-review.json`
- **THEN** 产物中新增 `reference_documents_used` 字段，格式同上

## MODIFIED Requirements

### Requirement: build_codebase_context 返回值扩展

`build_codebase_context` 函数的返回值 SHALL 包含 `reference_documents` 字段，使参考文档随 codebase context 一起传递给下游 Agent。

#### Scenario: 返回值包含参考文档

- **WHEN** `build_codebase_context` 被调用且 `reference_config.enabled` 为 `true`
- **THEN** 返回值中新增 `reference_documents` 字段
- **AND** 该字段值为 `registry.get_documents_for_stage("solution_design", max_total_chars=config.reference.max_chars_per_stage)` 的结果
- **WHEN** `reference_config.enabled` 为 `false` 或 `reference_config` 为 `None`
- **THEN** `reference_documents` 字段值为空列表 `[]`

## REMOVED Requirements

无移除的需求。
