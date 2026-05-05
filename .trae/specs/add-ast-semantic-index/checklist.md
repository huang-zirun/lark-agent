# Checklist

## 数据模型与解析器

- [x] `SemanticNode` dataclass 包含 id, type, name, qualified_name, file_path, line_start, line_end, signature, docstring, modifiers 字段
- [x] `SemanticRelation` dataclass 包含 source, target, type, evidence 字段
- [x] `NodeType` 枚举包含 module, class, function, method, variable, import, parameter, decorator
- [x] `RelationType` 枚举包含 contains, imports, calls, inherits, implements, references, decorates
- [x] Python AST 解析器能正确提取 ClassDef、FunctionDef、AsyncFunctionDef、Import、ImportFrom 节点
- [x] Python AST 解析器能提取函数签名（参数列表 + 返回注解）和 docstring
- [x] Python AST 解析器能提取继承关系（ClassDef.bases）
- [x] Python AST 解析器能启发式提取调用关系（ast.Call → Name/Attribute）
- [x] Python AST 解析器对语法错误文件返回部分结果 + 错误状态，不抛异常
- [x] tree-sitter JS/TS 解析器能提取 function_declaration, class_declaration, import_statement, call_expression
- [x] tree-sitter JS/TS 解析器能提取类继承（extends/implements）
- [x] tree-sitter 未安装时优雅降级，返回 unavailable 状态
- [x] ParserRegistry 按文件后缀正确分发到对应解析器
- [x] 非编程语言文件仅记录文件级元数据，不尝试 AST 解析
- [x] 单文件解析超时保护生效

## 索引构建

- [x] 全量索引构建能遍历 workspace 所有文件并生成 symbols.json, relations.json, file_meta.json, summary.json
- [x] 增量索引更新通过 SHA256 哈希对比识别新增/修改/删除文件
- [x] 修改文件时旧符号和关系被正确移除，新解析结果被正确添加
- [x] 删除文件时对应符号和关系被正确移除
- [x] 索引文件采用"写临时文件 → 原子重命名"策略
- [x] 索引版本不匹配时自动触发全量重建
- [x] 单文件符号数超限时截断并标记 truncated: true
- [x] 排除目录（.git, node_modules, __pycache__, .venv, artifacts, .devflow-index）生效

## 语义查询

- [x] symbol_search 能按名称模式查找符号，返回匹配的 SemanticNode 列表
- [x] find_references 能查找引用指定符号的所有位置
- [x] find_callers 能查找调用指定函数的所有调用者
- [x] find_hierarchy 能查找类的完整继承链
- [x] find_dependencies 能查找文件的导入和被导入关系
- [x] 查询结果超过 50 条时返回 truncated: true 和 total_count
- [x] 内存索引使用 HashMap 实现 O(1) 符号查找和引用查询

## 工具集成

- [x] CodeToolExecutor.execute 支持 semantic_search 工具分发
- [x] CodeToolExecutor.semantic_search 方法正确调用查询引擎
- [x] 索引不存在时 semantic_search 自动触发索引构建
- [x] ReviewToolExecutor 的 READ_ONLY_TOOLS 包含 semantic_search
- [x] semantic_search 事件被正确记录到 events 列表

## 上下文增强

- [x] build_codebase_context 返回字典包含 semantic_summary 字段
- [x] build_codebase_context 返回字典包含 semantic_symbols 字段（按文件分组的顶层符号列表）
- [x] build_codebase_context 返回字典包含 semantic_relations_count 字段
- [x] 语义索引构建失败时 semantic_summary 标记为 unavailable，不影响现有输出
- [x] semantic.enabled=false 时跳过索引构建，semantic_summary 标记为 disabled

## 配置

- [x] SemanticConfig dataclass 包含 enabled, max_workers, parse_timeout_seconds, max_symbols_per_file, index_dir_name 字段
- [x] DevflowConfig 包含 semantic 字段
- [x] load_config 正确解析 semantic 配置段
- [x] config.example.json 包含 semantic 配置示例
- [x] SemanticConfig 各字段有合理的默认值

## CLI

- [x] `devflow semantic index --workspace <path>` 命令可执行全量/增量索引构建
- [x] 索引构建摘要输出到 stdout

## 测试

- [x] Python AST 解析器测试通过（正常文件、语法错误、嵌套结构）
- [x] tree-sitter JS/TS 解析器测试通过（正常文件、未安装降级）
- [x] 索引构建测试通过（全量、增量、文件删除、版本不匹配）
- [x] 语义查询测试通过（符号查找、引用、调用链、继承链、依赖）
- [x] CodeToolExecutor.semantic_search 集成测试通过
- [x] build_codebase_context 语义增强测试通过
- [x] 配置加载测试通过（默认值、显式配置、enabled=false）
