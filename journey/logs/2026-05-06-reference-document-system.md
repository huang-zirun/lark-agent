# 2026-05-06 参考文档体系实现

## 概述

基于竞品 orchestration-engine 的参考文档体系调研，以 clean room 方式实现了 12 个行业规范参考文档，按需注入到各阶段 Agent 的 prompt 中。

## 变更范围

### 新增文件

- `devflow/references/__init__.py` — 包导出
- `devflow/references/registry.py` — `ReferenceRegistry` 核心模块
- `devflow/references/ears-syntax.md` — EARS 需求语法模式
- `devflow/references/nfr-checklist.md` — 非功能需求检查清单
- `devflow/references/adr-template.md` — 架构决策记录模板
- `devflow/references/tech-selection.md` — 技术选型评估框架
- `devflow/references/layered-architecture.md` — 分层架构模式
- `devflow/references/api-design.md` — REST API 设计指南
- `devflow/references/db-schema.md` — 数据库 Schema 设计原则
- `devflow/references/auth-flow.md` — 认证授权流程模式
- `devflow/references/git-conventions.md` — Git 分支与提交约定
- `devflow/references/env-management.md` — 环境与配置管理策略
- `devflow/references/testing-strategy.md` — 测试策略与覆盖率目标
- `devflow/references/release-checklist.md` — 发布就绪检查清单
- `tests/test_reference_registry.py` — 33 个单元测试

### 修改文件

- `devflow/config.py` — 新增 `ReferenceConfig` 数据类
- `config.example.json` — 新增 `reference` 配置段
- `devflow/solution/workspace.py` — `build_codebase_context` 增加 `reference_documents` 返回字段
- `devflow/solution/designer.py` — 传递 `reference_config`，注入 `reference_documents`，记录 `reference_documents_used`
- `devflow/solution/prompt.py` — 增加"参考文档使用"指引
- `devflow/intake/analyzer.py` — 注入参考文档到需求分析 prompt
- `devflow/intake/prompt.py` — 增加"参考文档使用"指引
- `devflow/code/prompt.py` + `devflow/code/agent.py` — 代码生成 Agent 注入
- `devflow/test/prompt.py` + `devflow/test/agent.py` — 测试生成 Agent 注入
- `devflow/review/prompt.py` + `devflow/review/agent.py` — 代码评审 Agent 注入 + `reference_documents_used` 追溯
- `devflow/pipeline.py` — 3 处调用点传递 `reference_config=config.reference`

## 关键设计决策

1. **Clean room 实现**：所有 12 个文档内容基于公开行业标准（ISO、RFC、OWASP 等），不引用任何私有实现
2. **懒加载 + 缓存**：启动时只建轻量索引（YAML front matter），首次使用才加载正文并缓存
3. **Token 预算可控**：`max_chars_per_stage`（默认 4000）+ `max_chars_per_document`（默认 2000）+ `priority` 排序
4. **产物可追溯**：`solution.json` 和 `code-review.json` 记录 `reference_documents_used`
5. **优雅降级**：`reference.enabled=false` 时所有 Agent 正常工作

## 验证结果

- 33 个单元测试全部通过
- 端到端冒烟测试通过：各阶段文档匹配正确
  - solution_design: adr-template, tech-selection, layered-architecture
  - requirement_intake: ears-syntax, nfr-checklist
  - code_generation: git-conventions, env-management
  - test_generation: testing-strategy
  - code_review: nfr-checklist, release-checklist

## Spec 文件

- `.trae/specs/add-reference-document-system/spec.md`
- `.trae/specs/add-reference-document-system/tasks.md`
- `.trae/specs/add-reference-document-system/checklist.md`
