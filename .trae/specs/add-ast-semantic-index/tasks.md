# Tasks

- [x] Task 1: 创建语义节点模型与数据结构定义
  - [x] SubTask 1.1: 创建 `devflow/semantic/__init__.py` 包入口
  - [x] SubTask 1.2: 创建 `devflow/semantic/models.py`，定义 `SemanticNode`、`SemanticRelation`、`FileMeta`、`IndexSummary` dataclass
  - [x] SubTask 1.3: 定义节点类型枚举 `NodeType`（module, class, function, method, variable, import, parameter, decorator）
  - [x] SubTask 1.4: 定义关系类型枚举 `RelationType`（contains, imports, calls, inherits, implements, references, decorates）

- [x] Task 2: 实现 Python AST 解析器
  - [x] SubTask 2.1: 创建 `devflow/semantic/parsers/python_parser.py`
  - [x] SubTask 2.2: 实现 `PythonSemanticVisitor(ast.NodeVisitor)`，遍历 ClassDef/FunctionDef/AsyncFunctionDef/Import/ImportFrom/Assign/Call 节点
  - [x] SubTask 2.3: 提取函数签名（参数列表 + 返回注解）、docstring、装饰器、继承关系
  - [x] SubTask 2.4: 实现调用关系启发式解析（Name → 直接调用，Attribute → obj.method 调用）
  - [x] SubTask 2.5: 处理语法错误文件的容错逻辑（捕获 SyntaxError，返回部分结果 + 错误状态）

- [x] Task 3: 实现 tree-sitter JS/TS 解析器
  - [x] SubTask 3.1: 创建 `devflow/semantic/parsers/jsts_parser.py`
  - [x] SubTask 3.2: 实现 tree-sitter 延迟导入与安装检测（`tree-sitter`、`tree-sitter-javascript`、`tree-sitter-typescript`）
  - [x] SubTask 3.3: 实现 JS/TS AST 遍历，提取 function_declaration、class_declaration、import_statement、call_expression、method_definition、variable_declarator
  - [x] SubTask 3.4: 提取类继承（heritage_clause extends/implements）
  - [x] SubTask 3.5: 实现 tree-sitter 未安装时的优雅降级（返回空结果 + unavailable 状态）

- [x] Task 4: 实现解析器适配层
  - [x] SubTask 4.1: 创建 `devflow/semantic/parsers/__init__.py`
  - [x] SubTask 4.2: 实现 `ParserRegistry`，按文件后缀分发到对应解析器
  - [x] SubTask 4.3: 实现纯文本回退解析器（非编程语言文件仅记录元数据）
  - [x] SubTask 4.4: 实现单文件解析超时保护

- [x] Task 5: 实现索引构建器
  - [x] SubTask 5.1: 创建 `devflow/semantic/indexer.py`
  - [x] SubTask 5.2: 实现全量索引构建（遍历文件 → 并行解析 → 聚合符号/关系 → 写入索引文件）
  - [x] SubTask 5.3: 实现增量索引更新（SHA256 哈希对比 → 识别变更 → 局部重建 → 原子写入）
  - [x] SubTask 5.4: 实现索引文件 I/O（symbols.json、relations.json、file_meta.json、summary.json 的读写）
  - [x] SubTask 5.5: 实现符号截断逻辑（单文件符号数超限处理）
  - [x] SubTask 5.6: 实现索引版本兼容检查（版本不匹配触发全量重建）

- [x] Task 6: 实现语义查询引擎
  - [x] SubTask 6.1: 创建 `devflow/semantic/query.py`
  - [x] SubTask 6.2: 实现内存索引加载与缓存（HashMap: name → symbol_ids, target_id → edges）
  - [x] SubTask 6.3: 实现 `symbol_search(pattern)` — 符号名称模糊/精确查找
  - [x] SubTask 6.4: 实现 `find_references(symbol_id)` — 引用位置查询
  - [x] SubTask 6.5: 实现 `find_callers(symbol_name)` — 调用链查询
  - [x] SubTask 6.6: 实现 `find_hierarchy(symbol_name)` — 继承链查询
  - [x] SubTask 6.7: 实现 `find_dependencies(file_path)` — 模块依赖查询
  - [x] SubTask 6.8: 实现查询结果限制（max 50 条 + truncated 标记）

- [x] Task 7: 扩展配置模型
  - [x] SubTask 7.1: 在 `devflow/config.py` 中新增 `SemanticConfig` dataclass（enabled, max_workers, parse_timeout_seconds, max_symbols_per_file, index_dir_name）
  - [x] SubTask 7.2: 在 `DevflowConfig` 中新增 `semantic` 字段
  - [x] SubTask 7.3: 在 `load_config` 中解析 `semantic` 配置段
  - [x] SubTask 7.4: 在 `config.example.json` 中添加 `semantic` 配置示例

- [x] Task 8: 集成到 CodeToolExecutor 和 ReviewToolExecutor
  - [x] SubTask 8.1: 在 `CodeToolExecutor` 中新增 `semantic_search` 工具分发
  - [x] SubTask 8.2: 实现 `semantic_search` 方法（调用查询引擎，自动触发索引构建）
  - [x] SubTask 8.3: 在 `ReviewToolExecutor` 的 `READ_ONLY_TOOLS` 中新增 `semantic_search`
  - [x] SubTask 8.4: 在 `CodeToolExecutor._record` 中支持 `semantic_search` 事件记录

- [x] Task 9: 集成到 build_codebase_context
  - [x] SubTask 9.1: 在 `build_codebase_context` 中调用索引构建器（根据 `SemanticConfig.enabled` 决定是否执行）
  - [x] SubTask 9.2: 在返回字典中附加 `semantic_summary`、`semantic_symbols`、`semantic_relations_count`
  - [x] SubTask 9.3: 实现索引构建失败的降级逻辑（标记 unavailable，不影响现有输出）

- [x] Task 10: 添加 CLI 命令
  - [x] SubTask 10.1: 在 `devflow/cli.py` 中新增 `devflow semantic index` 子命令
  - [x] SubTask 10.2: 输出索引构建摘要到 stdout

- [x] Task 11: 编写测试
  - [x] SubTask 11.1: 测试 Python AST 解析器（正常文件、语法错误文件、嵌套类/函数）
  - [x] SubTask 11.2: 测试 tree-sitter JS/TS 解析器（正常文件、未安装降级）
  - [x] SubTask 11.3: 测试索引构建（全量、增量、文件删除、版本不匹配）
  - [x] SubTask 11.4: 测试语义查询（符号查找、引用查询、调用链、继承链、依赖查询）
  - [x] SubTask 11.5: 测试 CodeToolExecutor.semantic_search 集成
  - [x] SubTask 11.6: 测试 build_codebase_context 语义增强输出
  - [x] SubTask 11.7: 测试配置加载（SemanticConfig 默认值、显式配置、enabled=false）

# Task Dependencies

- Task 2 依赖 Task 1（解析器产出 SemanticNode/SemanticRelation）
- Task 3 依赖 Task 1
- Task 4 依赖 Task 2、Task 3
- Task 5 依赖 Task 4
- Task 6 依赖 Task 1、Task 5
- Task 8 依赖 Task 6
- Task 9 依赖 Task 5、Task 7
- Task 10 依赖 Task 5
- Task 11 依赖 Task 1-10 全部完成
- Task 7 可与 Task 2-4 并行
