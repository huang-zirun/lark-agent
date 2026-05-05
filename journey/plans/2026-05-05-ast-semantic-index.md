# AST Semantic Index Implementation Plan

## Goal

Add AST-based semantic indexing to the DevFlow Engine, providing structured code understanding for all agents (solution design, code generation, code review).

## Design Decisions

- Python files: use built-in `ast` module (zero dependency)
- JS/TS files: use `tree-sitter` with lazy import and graceful degradation
- Index storage: JSON files under `{workspace}/.devflow-index/`
- Incremental updates: SHA256 hash-based change detection
- Query engine: in-memory HashMap for O(1) lookups
- 5 query types: symbol, references, callers, hierarchy, dependencies

## Implementation Steps

1. Create `devflow/semantic/` package with models (SemanticNode, SemanticRelation, FileMeta, IndexSummary, NodeType, RelationType, ParseStatus)
2. Implement Python AST parser (PythonSemanticVisitor)
3. Implement tree-sitter JS/TS parser (JsTsVisitor) with lazy import
4. Implement parser registry (ParserRegistry) with language detection and timeout protection
5. Implement indexer (SemanticIndexer) with full/incremental build, atomic writes
6. Implement query engine (SemanticQueryEngine) with 5 query types
7. Extend config (SemanticConfig in config.py)
8. Integrate into CodeToolExecutor and ReviewToolExecutor
9. Integrate into build_codebase_context
10. Add CLI command `devflow semantic index`
11. Write tests (49 test cases)

## Verification

- All 49 tests pass (47 passed, 2 skipped for tree-sitter)
- All 35 checklist items verified
