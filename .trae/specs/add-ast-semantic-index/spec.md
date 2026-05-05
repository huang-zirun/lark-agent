# 代码库语义索引（AST Semantic Index）Spec

## Why

当前 DevFlow Engine 的代码库上下文构建（`build_codebase_context`）仅基于纯文本读取与正则截断，`CodeToolExecutor` 的 `glob_search` 和 `grep_search` 也只支持文件名匹配和行级正则搜索。这导致：

1. **Solution Design Agent** 收到的代码库上下文缺乏结构化语义信息（如函数签名、类继承关系、调用链），LLM 需要从原始文本中自行推断，消耗大量 Token 且容易出错。
2. **Code Generation / Review Agent** 的工具层无法执行语义查询（如"查找调用 `resolve_workspace` 的所有位置"或"列出 `CodeToolExecutor` 的所有方法"），只能退化为全文 grep。
3. 增量场景下，每次构建上下文都需重新遍历全部文件，无变更检测能力。

本 Spec 旨在引入基于 AST 的语义索引，为 DevFlow 各 Agent 提供结构化的代码理解能力，降低 LLM 推理负担，提升方案设计与代码生成的准确性。

## What Changes

- **新增 `devflow/semantic/` 包**：核心语义索引模块，包含 AST 解析器适配层、语义信息提取器、索引构建器、查询引擎。
- **新增 AST 解析器适配层**：支持 Python（内置 `ast` 模块）、JavaScript/TypeScript（通过 `tree-sitter` 统一解析）、以及纯文本回退。
- **新增语义节点模型**：定义统一的语义节点类型（Module、Class、Function、Variable、Import、Call、Inheritance 等）。
- **新增索引数据结构**：基于 JSON 的持久化索引，包含符号表、引用关系图、文件级摘要。
- **新增增量更新机制**：基于文件哈希的变更检测，仅重新解析变更文件并更新索引。
- **扩展 `build_codebase_context`**：在现有文本上下文基础上附加语义索引摘要。
- **扩展 `CodeToolExecutor`**：新增 `semantic_search` 工具，支持符号查找、引用查询、继承链查询。
- **扩展 `ReviewToolExecutor`**：同步支持 `semantic_search` 只读查询。
- **扩展配置**：`config.json` 新增 `semantic` 配置段，控制索引行为。

## Impact

- Affected specs: `devflow.solution_design.v1`（codebase_context 字段扩展）、`devflow.code_generation.v1`（工具列表扩展）
- Affected code:
  - `devflow/solution/workspace.py` — `build_codebase_context` 集成语义索引
  - `devflow/code/tools.py` — `CodeToolExecutor` 新增 `semantic_search`
  - `devflow/review/tools.py` — `ReviewToolExecutor` 同步扩展
  - `devflow/config.py` — 新增 `SemanticConfig`
  - 新增 `devflow/semantic/` 包（~6 个模块）
- 无 Breaking Changes：现有 API 行为保持不变，语义索引为增量增强

---

## ADDED Requirements

### Requirement: AST 解析器适配层

系统 SHALL 提供统一的 AST 解析器适配接口，支持多种编程语言的代码解析。

#### Scenario: 解析 Python 文件
- **GIVEN** 一个 `.py` 后缀的文件
- **WHEN** 解析器处理该文件
- **THEN** 使用 Python 内置 `ast` 模块解析，提取 Module、ClassDef、FunctionDef、AsyncFunctionDef、Import/ImportFrom、Assign、Call 等节点

#### Scenario: 解析 JavaScript/TypeScript 文件
- **GIVEN** 一个 `.js`/`.jsx`/`.ts`/`.tsx` 后缀的文件
- **WHEN** 解析器处理该文件
- **THEN** 使用 `tree-sitter` + `tree-sitter-javascript` / `tree-sitter-typescript` 解析，提取 program、function_declaration、class_declaration、import_statement、call_expression 等节点

#### Scenario: 解析 HTML/CSS/JSON/YAML 等非编程语言文件
- **GIVEN** 一个非编程语言后缀的文件
- **WHEN** 解析器处理该文件
- **THEN** 跳过 AST 解析，仅记录文件级元数据（路径、大小、行数）

#### Scenario: 解析语法错误的文件
- **GIVEN** 一个包含语法错误的源文件
- **WHEN** 解析器处理该文件
- **THEN** 捕获 `SyntaxError`，记录解析失败状态和错误信息，不中断整体索引构建

### Requirement: 语义节点模型

系统 SHALL 定义统一的语义节点模型，跨语言抽象代码结构。

#### Scenario: 符号节点提取
- **WHEN** AST 解析完成
- **THEN** 为每个可识别的代码结构生成语义节点，包含以下字段：
  - `id`：全局唯一标识（格式 `{file_path}:{node_type}:{name}:{line}`）
  - `type`：节点类型枚举（`module` | `class` | `function` | `method` | `variable` | `import` | `parameter` | `decorator`）
  - `name`：符号名称
  - `qualified_name`：完全限定名（如 `devflow.code.tools.CodeToolExecutor.read_file`）
  - `file_path`：相对文件路径
  - `line_start` / `line_end`：起止行号
  - `signature`：函数/方法签名（参数列表 + 返回类型注解）
  - `docstring`：文档字符串（如有）
  - `modifiers`：修饰符列表（如 `async`、`static`、`private`、`public`）

#### Scenario: 关系边提取
- **WHEN** AST 解析完成
- **THEN** 提取以下关系类型：
  - `contains`：父节点包含子节点（Module → Class → Method）
  - `imports`：导入关系（从哪个模块导入什么符号）
  - `calls`：函数调用关系（调用者 → 被调用者）
  - `inherits`：类继承关系（子类 → 父类）
  - `implements`：接口实现（实现类 → 接口）
  - `references`：变量引用（引用位置 → 定义位置）
  - `decorates`：装饰器应用（装饰器 → 被装饰对象）

### Requirement: 索引数据结构设计

系统 SHALL 设计高效的索引数据结构，平衡查询效率与存储开销。

#### Scenario: 索引持久化格式
- **WHEN** 索引构建完成
- **THEN** 将索引写入 `{workspace}/.devflow-index/` 目录，包含以下文件：
  - `symbols.json`：符号表（所有语义节点的扁平列表，按 file_path 分组）
  - `relations.json`：关系边列表（源 ID → 目标 ID + 关系类型）
  - `file_meta.json`：文件级元数据（路径、哈希、行数、语言、解析状态、最后索引时间）
  - `summary.json`：索引摘要（总符号数、总关系数、语言分布、构建时间、索引版本）

#### Scenario: 索引版本兼容
- **GIVEN** 索引文件已存在
- **WHEN** 索引版本与当前代码期望版本不匹配
- **THEN** 自动触发全量重建，旧索引被替换

#### Scenario: 索引大小控制
- **WHEN** 单个文件的语义节点超过 500 个
- **THEN** 仅保留顶层定义（class、function、import），嵌套定义截断并标记 `truncated: true`

### Requirement: 索引构建流程

系统 SHALL 提供完整的索引构建流程，支持全量构建与增量更新。

#### Scenario: 全量索引构建
- **WHEN** 执行 `devflow semantic index --workspace <path>` 或索引目录不存在
- **THEN** 系统执行以下步骤：
  1. 遍历 workspace 下所有文件（排除 `.git`、`node_modules`、`__pycache__`、`.venv`、`artifacts`、`.devflow-index` 等目录）
  2. 按文件后缀选择对应解析器
  3. 并行解析文件（最大并发数由 `semantic.max_workers` 控制，默认 4）
  4. 提取语义节点和关系边
  5. 构建全局符号表和关系图
  6. 写入索引文件到 `.devflow-index/`
  7. 输出构建摘要到 stdout

#### Scenario: 增量索引更新
- **GIVEN** 索引目录已存在且版本匹配
- **WHEN** 执行 `devflow semantic index --workspace <path>` 或 `build_codebase_context` 触发索引
- **THEN** 系统执行以下步骤：
  1. 读取 `file_meta.json`，获取已索引文件的 SHA256 哈希
  2. 重新计算当前文件的 SHA256 哈希
  3. 对比哈希，识别新增、修改、删除的文件
  4. 仅对变更文件重新解析，复用未变更文件的索引结果
  5. 更新符号表和关系图（移除旧文件的符号和关系，加入新解析结果）
  6. 更新 `file_meta.json` 和 `summary.json`

#### Scenario: 文件删除处理
- **GIVEN** 索引中存在文件 `a.py` 的记录
- **WHEN** `a.py` 已从 workspace 中删除
- **THEN** 从符号表和关系图中移除该文件的所有节点和边，更新 `file_meta.json`

#### Scenario: 构建超时保护
- **WHEN** 单文件解析耗时超过 `semantic.parse_timeout_seconds`（默认 10 秒）
- **THEN** 中断该文件解析，标记为 `timeout`，继续处理其他文件

### Requirement: 语义查询功能

系统 SHALL 提供语义查询引擎，支持结构化代码查询。

#### Scenario: 符号查找
- **WHEN** 调用 `semantic_search` 工具，参数 `query_type = "symbol"`，`pattern = "CodeToolExecutor"`
- **THEN** 返回所有名称匹配 `CodeToolExecutor` 的符号节点列表，包含：
  - `id`、`type`、`name`、`qualified_name`、`file_path`、`line_start`、`signature`、`docstring`

#### Scenario: 引用查询
- **WHEN** 调用 `semantic_search` 工具，参数 `query_type = "references"`，`symbol_id = "devflow/code/tools.py:class:CodeToolExecutor:21"`
- **THEN** 返回所有引用该符号的位置列表（通过 `references` 和 `inherits` 关系边查找）

#### Scenario: 调用链查询
- **WHEN** 调用 `semantic_search` 工具，参数 `query_type = "callers"`，`symbol_name = "resolve_workspace_path"`
- **THEN** 返回所有调用 `resolve_workspace_path` 的函数/方法列表

#### Scenario: 继承链查询
- **WHEN** 调用 `semantic_search` 工具，参数 `query_type = "hierarchy"`，`symbol_name = "CodeToolExecutor"`
- **THEN** 返回该类的完整继承链（父类、子类）

#### Scenario: 模块依赖查询
- **WHEN** 调用 `semantic_search` 工具，参数 `query_type = "dependencies"`，`file_path = "devflow/code/tools.py"`
- **THEN** 返回该文件导入的所有模块列表，以及被哪些文件导入

#### Scenario: 查询结果限制
- **WHEN** 查询匹配结果超过 50 条
- **THEN** 返回前 50 条，并在结果中标记 `truncated: true` 和 `total_count`

### Requirement: CodeToolExecutor 语义搜索集成

系统 SHALL 在 `CodeToolExecutor` 中新增 `semantic_search` 工具。

#### Scenario: Agent 调用语义搜索
- **WHEN** Code Generation Agent 调用 `semantic_search` 工具
- **THEN** `CodeToolExecutor.execute` 分发到语义查询引擎，返回查询结果

#### Scenario: 索引不存在时自动构建
- **WHEN** `semantic_search` 被调用但索引目录不存在
- **THEN** 自动触发增量索引构建（首次为全量构建），构建完成后再执行查询

#### Scenario: ReviewToolExecutor 只读语义搜索
- **WHEN** Code Review Agent 通过 `ReviewToolExecutor` 调用 `semantic_search`
- **THEN** 查询正常执行，`semantic_search` 被加入 `READ_ONLY_TOOLS` 集合

### Requirement: build_codebase_context 语义增强

系统 SHALL 在 `build_codebase_context` 输出中附加语义索引摘要。

#### Scenario: 上下文输出扩展
- **WHEN** `build_codebase_context` 被调用
- **THEN** 在返回的字典中新增以下字段：
  - `semantic_summary`：索引摘要（总符号数、总关系数、语言分布）
  - `semantic_symbols`：按文件分组的顶层符号列表（class、function、import），每个符号包含 `name`、`type`、`line_start`、`signature`
  - `semantic_relations_count`：各关系类型的计数

#### Scenario: 索引构建失败降级
- **WHEN** 语义索引构建失败（如 tree-sitter 未安装、文件解析全部失败）
- **THEN** `semantic_summary` 标记为 `{"status": "unavailable", "error": "..."}`，其余语义字段为空，不影响现有文本上下文的生成

### Requirement: 配置扩展

系统 SHALL 在 `config.json` 中新增 `semantic` 配置段。

#### Scenario: 语义索引配置
- **WHEN** 加载配置文件
- **THEN** 解析 `semantic` 段，包含以下字段：
  - `enabled`：是否启用语义索引（默认 `true`）
  - `max_workers`：并行解析最大工作线程数（默认 `4`）
  - `parse_timeout_seconds`：单文件解析超时（默认 `10`）
  - `max_symbols_per_file`：单文件最大符号数（默认 `500`）
  - `index_dir_name`：索引目录名（默认 `.devflow-index`）

#### Scenario: 语义索引禁用
- **GIVEN** `semantic.enabled` 为 `false`
- **WHEN** `build_codebase_context` 被调用
- **THEN** 跳过语义索引构建，`semantic_summary` 标记为 `{"status": "disabled"}`

---

## MODIFIED Requirements

### Requirement: CodeToolExecutor 工具分发
- `CodeToolExecutor.execute` 方法需新增 `semantic_search` 工具分发分支，调用语义查询引擎

### Requirement: ReviewToolExecutor 只读工具集
- `READ_ONLY_TOOLS` 集合需新增 `semantic_search`

### Requirement: build_codebase_context 返回结构
- 返回字典需新增 `semantic_summary`、`semantic_symbols`、`semantic_relations_count` 字段

### Requirement: DevflowConfig 配置模型
- 新增 `SemanticConfig` dataclass，`DevflowConfig` 新增 `semantic` 字段

---

## REMOVED Requirements

无

---

## 附录：技术选型分析

### A. 代码解析工具选型对比

| 特性 | Python `ast` | tree-sitter | Babel Parser | TypeScript Compiler API | Esprima |
|------|-------------|-------------|--------------|------------------------|---------|
| 语言支持 | 仅 Python | 50+ 语言（含 JS/TS） | JS/JSX | TS/TSX | JS |
| 安装方式 | 内置，零依赖 | pip 安装，含预编译二进制 | npm 包，需 Node.js | npm 包，需 Node.js | npm 包，需 Node.js |
| 解析速度 | 快（C 实现） | 极快（C 库 + WASM） | 中等 | 慢（完整类型检查） | 快 |
| 语法容错 | 严格，语法错误即失败 | 容错，生成部分 AST | 容错 | 严格 | 严格 |
| 类型信息 | 无（需额外工具） | 无 | 无 | 有（完整类型系统） | 无 |
| 增量解析 | 不支持 | 支持（tree-sitter 特性） | 不支持 | 不支持 | 不支持 |
| Python 绑定 | 原生 | `tree-sitter` Python 包 | 无（需 subprocess） | 无（需 subprocess） | 无（需 subprocess） |

**选型决策**：
- **Python 文件**：使用内置 `ast` 模块。零依赖、速度快、与 CPython 完全兼容。通过 `ast.walk` + 自定义 Visitor 实现语义提取。
- **JavaScript/TypeScript 文件**：使用 `tree-sitter` + `tree-sitter-javascript` / `tree-sitter-typescript`。理由：
  1. 纯 Python 绑定，无需 Node.js 运行时
  2. 语法容错能力强，适合解析可能不完整的工作区代码
  3. 统一的查询接口（`tree-sitter` query），便于跨语言适配
  4. 解析速度极快（C 库级别）
- **其他语言**：v1 阶段仅支持 Python 和 JS/TS，其余文件仅记录文件级元数据

### B. AST 节点类型分析与关键语义信息提取策略

**Python AST 提取策略**：
- `ast.Module` → `module` 节点
- `ast.ClassDef` → `class` 节点，提取 `name`、`bases`（继承关系）、`decorator_list`
- `ast.FunctionDef` / `ast.AsyncFunctionDef` → `function`/`method` 节点，提取 `name`、`args`（参数列表）、`returns`（返回注解）、`decorator_list`
- `ast.Import` / `ast.ImportFrom` → `import` 节点，提取 `module`、`names`
- `ast.Call` → `calls` 关系边，提取 `func` 属性（需启发式解析调用目标）
- `ast.Attribute` → 辅助解析 `self.method()` 等方法调用
- `ast.Assign` / `ast.AnnAssign` → `variable` 节点

**JavaScript/TypeScript tree-sitter 提取策略**：
- `program` → `module` 节点
- `function_declaration` / `arrow_function` / `function_expression` → `function` 节点
- `class_declaration` → `class` 节点，提取 `heritage_clause`（extends/implements）
- `import_statement` / `import_clause` → `import` 节点
- `call_expression` → `calls` 关系边
- `method_definition` → `method` 节点
- `variable_declarator` → `variable` 节点
- `decorator` → `decorator` 节点

**调用关系解析的启发式策略**：
- Python：对 `ast.Call` 的 `func` 字段，若为 `ast.Name` 则直接提取名称；若为 `ast.Attribute` 则尝试拼接 `obj.method`；`self.method()` 在类上下文中解析为当前类的方法调用
- JS/TS：对 `call_expression` 的 `function` 字段，若为 `identifier` 直接提取；若为 `member_expression` 则拼接 `obj.method`
- 跨文件调用解析：v1 阶段仅记录调用名称，不进行跨文件符号解析（需类型系统支持，留作 v2）

### C. 索引数据结构设计

**符号表 `symbols.json`**：
```json
{
  "version": "devflow.semantic_index.v1",
  "files": {
    "devflow/code/tools.py": {
      "language": "python",
      "symbols": [
        {
          "id": "devflow/code/tools.py:class:CodeToolExecutor:21",
          "type": "class",
          "name": "CodeToolExecutor",
          "qualified_name": "devflow.code.tools.CodeToolExecutor",
          "line_start": 21,
          "line_end": 169,
          "docstring": "代码工具执行器...",
          "modifiers": ["slots"],
          "children": [
            "devflow/code/tools.py:method:__post_init__:27",
            "devflow/code/tools.py:method:execute:29",
            "devflow/code/tools.py:method:read_file:57"
          ]
        }
      ]
    }
  }
}
```

**关系图 `relations.json`**：
```json
{
  "version": "devflow.semantic_index.v1",
  "edges": [
    {
      "source": "devflow/code/tools.py:class:CodeToolExecutor:21",
      "target": "devflow/code/permissions.py:function:resolve_workspace_path:5",
      "type": "calls",
      "evidence": {"file": "devflow/code/tools.py", "line": 58}
    },
    {
      "source": "devflow/review/tools.py:class:ReviewToolExecutor:13",
      "target": "devflow/code/tools.py:class:CodeToolExecutor:21",
      "type": "references",
      "evidence": {"file": "devflow/review/tools.py", "line": 20}
    }
  ]
}
```

**查询效率考量**：
- 符号查找：按 `name` 建立内存 HashMap（`name → [symbol_ids]`），O(1) 查找
- 引用查询：按 `target` 建立反向索引 HashMap（`target_id → [edges]`），O(1) 查找
- 继承链查询：按 `inherits` 类型过滤后 BFS 遍历
- 文件级查询：按 `file_path` 建立索引 HashMap

**存储开销估算**：
- 每个符号节点约 200-500 字节 JSON
- 每条关系边约 150-300 字节 JSON
- 以当前项目（~30 个 Python 文件）为例，预估索引大小约 50-100 KB
- 大型项目（1000+ 文件）预估索引大小约 2-5 MB

### D. 增量更新机制

**变更检测**：
- 使用 SHA256 哈希对比文件内容
- `file_meta.json` 记录每个文件的 `{path, hash, last_indexed_at, status}`
- 增量更新时：
  1. 扫描 workspace 文件列表
  2. 计算每个文件的 SHA256
  3. 与 `file_meta.json` 对比
  4. 新增文件 → 解析并添加
  5. 修改文件 → 删除旧符号/关系，重新解析添加
  6. 删除文件 → 删除对应符号/关系

**一致性保证**：
- 索引更新采用"写入临时文件 → 原子重命名"策略
- 构建过程中若中断，旧索引保持完整可用

### E. 性能优化建议

1. **并行解析**：使用 `concurrent.futures.ProcessPoolExecutor` 并行解析文件，`max_workers` 可配置
2. **懒加载索引**：索引文件按需加载到内存，符号表和关系图分别独立加载
3. **内存索引缓存**：`SemanticIndex` 对象在进程生命周期内缓存，避免重复加载
4. **跳过大型文件**：超过 `max_file_size_bytes`（默认 1 MB）的文件跳过 AST 解析
5. **跳过生成目录**：排除 `node_modules`、`.venv`、`__pycache__`、`artifacts`、`.devflow-index` 等
6. **符号截断**：单文件符号数超限时仅保留顶层定义
7. **tree-sitter 延迟导入**：`tree-sitter` 相关模块仅在首次解析 JS/TS 文件时导入，未安装时优雅降级
8. **索引构建超时**：整体索引构建超时由 `semantic.build_timeout_seconds` 控制（默认 60 秒）

### F. 技术可行性分析

**可行性评估**：
- Python `ast` 模块是标准库，零风险
- `tree-sitter` Python 绑定成熟（PyPI 下载量 > 100 万/月），支持 Windows/macOS/Linux
- `tree-sitter-javascript` 和 `tree-sitter-typescript` 均有预编译 wheel，安装简单
- 索引数据结构基于 JSON，与项目现有数据存储方式一致
- 增量更新基于 SHA256 哈希，实现简单可靠

**风险评估**：
- `tree-sitter` 的 Python 绑定在某些 Windows 环境可能需要 C 编译器 → 提供纯 `ast` 回退模式
- 跨文件调用解析在 v1 阶段为启发式，准确率约 70-80% → 在查询结果中标注置信度
- 大型代码库首次索引可能耗时较长 → 提供进度反馈和超时保护

### G. 预期效果评估

| 指标 | 当前（纯文本） | 引入语义索引后 |
|------|--------------|--------------|
| 代码库上下文 Token 消耗 | 高（原始文本截断） | 降低 30-50%（结构化摘要替代原始文本） |
| 符号查找准确率 | 低（grep 正则匹配） | 高（AST 精确提取） |
| 调用链查询能力 | 无 | 支持单跳调用链 |
| 增量更新效率 | 每次全量扫描 | 仅变更文件重解析 |
| Solution Design 质量 | 依赖 LLM 推断结构 | 提供结构化语义信息辅助 |
