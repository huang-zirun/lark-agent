# Tasks

- [ ] Task 1: 创建参考文档注册表核心模块
  - [ ] SubTask 1.1: 创建 `devflow/references/__init__.py`，导出 `ReferenceRegistry`
  - [ ] SubTask 1.2: 创建 `devflow/references/registry.py`，实现 `ReferenceRegistry` 类（元数据索引构建、懒加载、按需截断、章节提取、按阶段查询）
  - [ ] SubTask 1.3: 实现 YAML front matter 解析（仅读取 `---` 之间的内容，不加载正文）
  - [ ] SubTask 1.4: 实现章节提取（`_extract_section`：按 `## ` 级别标题切分）
  - [ ] SubTask 1.5: 实现按阶段查询 `get_documents_for_stage(stage_name, max_total_chars)`，按 priority 排序，累计字符数不超限

- [ ] Task 2: 扩展配置系统
  - [ ] SubTask 2.1: 在 `devflow/config.py` 中新增 `ReferenceConfig` 数据类（enabled, max_chars_per_stage, max_chars_per_document）
  - [ ] SubTask 2.2: 在 `DevflowConfig` 中新增 `reference: ReferenceConfig` 字段，默认值使用 `ReferenceConfig()`
  - [ ] SubTask 2.3: 更新 `config.example.json`，新增 `reference` 配置段

- [ ] Task 3: 编写 12 个行业规范参考文档
  - [ ] SubTask 3.1: 编写 `devflow/references/ears-syntax.md`（EARS 需求语法模式，基于 Mavin et al. RE 2009 + ISO 29148）
  - [ ] SubTask 3.2: 编写 `devflow/references/nfr-checklist.md`（非功能需求检查清单，基于 ISO 25010 + OWASP ASVS + Google SRE）
  - [ ] SubTask 3.3: 编写 `devflow/references/adr-template.md`（架构决策记录模板，基于 Nygard ADR + MADR + ISO 42010）
  - [ ] SubTask 3.4: 编写 `devflow/references/tech-selection.md`（技术选型评估框架，基于 ThoughtWorks Radar + AWS Well-Architected）
  - [ ] SubTask 3.5: 编写 `devflow/references/layered-architecture.md`（分层架构模式，基于 Fowler PEAA + Evans DDD + Clean Architecture）
  - [ ] SubTask 3.6: 编写 `devflow/references/api-design.md`（REST API 设计指南，基于 RFC 9110 + OpenAPI 3.1 + Zalando Guidelines）
  - [ ] SubTask 3.7: 编写 `devflow/references/db-schema.md`（数据库 Schema 设计原则，基于 SQL Style Guide + Flyway Best Practices）
  - [ ] SubTask 3.8: 编写 `devflow/references/auth-flow.md`（认证授权流程模式，基于 OWASP Cheat Sheets + RFC 6749/7636/7519）
  - [ ] SubTask 3.9: 编写 `devflow/references/git-conventions.md`（Git 分支与提交约定，基于 Conventional Commits 1.0 + SemVer 2.0）
  - [ ] SubTask 3.10: 编写 `devflow/references/env-management.md`（环境与配置管理策略，基于 12-Factor App + HashiCorp Vault）
  - [ ] SubTask 3.11: 编写 `devflow/references/testing-strategy.md`（测试策略与覆盖率目标，基于 Fowler Test Pyramid + ISTQB）
  - [ ] SubTask 3.12: 编写 `devflow/references/release-checklist.md`（发布就绪检查清单，基于 Google SRE + Atlassian Release Mgmt）

- [ ] Task 4: 修改 Agent prompt 构建逻辑，注入参考文档
  - [ ] SubTask 4.1: 修改 `devflow/solution/workspace.py` 的 `build_codebase_context`，接受 `reference_config` 参数，返回值增加 `reference_documents` 字段
  - [ ] SubTask 4.2: 修改 `devflow/solution/designer.py` 的 `build_solution_design_artifact`，传入 `reference_config`；修改 `build_solution_design_user_prompt`，在 payload 中增加 `reference_documents` 字段
  - [ ] SubTask 4.3: 修改 `devflow/solution/prompt.py` 的 `SOLUTION_DESIGN_ARCHITECT_PROMPT`，增加参考文档使用指引段落
  - [ ] SubTask 4.4: 修改 `devflow/intake/analyzer.py` 的 `build_llm_user_prompt`，在 payload 中增加 `reference_documents` 字段
  - [ ] SubTask 4.5: 修改 `devflow/intake/prompt.py` 的 `PRODUCT_REQUIREMENT_ANALYST_PROMPT`，增加参考文档使用指引
  - [ ] SubTask 4.6: 修改 `devflow/code/prompt.py` 的 `build_code_generation_user_prompt`，在 payload 中增加 `reference_documents` 字段；修改 `CODE_GENERATION_SYSTEM_PROMPT`
  - [ ] SubTask 4.7: 修改 `devflow/test/prompt.py` 的 `build_test_generation_user_prompt`，在 payload 中增加 `reference_documents` 字段；修改 `TEST_GENERATION_SYSTEM_PROMPT`
  - [ ] SubTask 4.8: 修改 `devflow/review/prompt.py` 的 `build_code_review_user_prompt`，在 payload 中增加 `reference_documents` 字段；修改 `CODE_REVIEW_SYSTEM_PROMPT`

- [ ] Task 5: 修改 pipeline 调用链，传递 reference_config
  - [ ] SubTask 5.1: 修改 `devflow/pipeline.py` 中各阶段执行函数，将 `config.reference` 传递到 Agent 调用
  - [ ] SubTask 5.2: 修改 `devflow/graph_runner.py`，确保 graph state 中包含 reference 配置信息

- [ ] Task 6: 产物可追溯性
  - [ ] SubTask 6.1: 修改 `devflow.solution_design.v1` 产物写入逻辑，新增 `reference_documents_used` 字段
  - [ ] SubTask 6.2: 修改 `devflow.code_review.v1` 产物写入逻辑，新增 `reference_documents_used` 字段

- [ ] Task 7: 验证与测试
  - [ ] SubTask 7.1: 编写 `tests/test_reference_registry.py`，测试索引构建、懒加载、章节提取、按阶段查询、字符截断
  - [ ] SubTask 7.2: 端到端验证：`devflow start --analyzer heuristic` 跑通完整 pipeline，确认参考文档注入正常
  - [ ] SubTask 7.3: 验证 `reference.enabled=false` 时所有 Agent 正常工作，无参考文档注入

# Task Dependencies

- [Task 2] depends on [Task 1]（配置系统需要引用 ReferenceRegistry）
- [Task 3] depends on [Task 1]（文档需要符合 registry 的 YAML front matter 格式）
- [Task 4] depends on [Task 1, Task 2, Task 3]（prompt 注入需要 registry + config + 文档内容）
- [Task 5] depends on [Task 2, Task 4]（pipeline 调用链需要 config 和 prompt 修改就绪）
- [Task 6] depends on [Task 4]（产物追溯需要 prompt 注入逻辑完成）
- [Task 7] depends on [Task 1-6]（验证需要所有功能就绪）
- [Task 3] 可与 [Task 1, Task 2] 并行（文档编写不依赖代码实现）
