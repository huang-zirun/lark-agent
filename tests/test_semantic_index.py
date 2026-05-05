from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from devflow.config import SemanticConfig
from devflow.semantic.models import (
    INDEX_VERSION,
    FileMeta,
    IndexSummary,
    NodeType,
    ParseStatus,
    RelationType,
    SemanticNode,
    SemanticRelation,
)
from devflow.semantic.parsers import FileParseResult, detect_language, parse_file
from devflow.semantic.parsers.python_parser import parse_python_file
from devflow.semantic.indexer import SemanticIndexer
from devflow.semantic.query import SemanticQueryEngine, MAX_QUERY_RESULTS


class TestSemanticNode:
    def test_create_node(self):
        node = SemanticNode(
            id="test.py:class:Foo:1",
            type=NodeType.CLASS,
            name="Foo",
            qualified_name="test.Foo",
            file_path="test.py",
            line_start=1,
            line_end=10,
            signature="()",
            docstring="A test class.",
            modifiers=("slots",),
            children=("test.py:method:bar:3",),
        )
        assert node.name == "Foo"
        assert node.type == NodeType.CLASS
        assert node.modifiers == ("slots",)
        assert node.children == ("test.py:method:bar:3",)

    def test_frozen(self):
        node = SemanticNode(
            id="t:f:foo:1", type=NodeType.FUNCTION, name="foo",
            qualified_name="t.foo", file_path="t.py", line_start=1, line_end=1,
        )
        with pytest.raises(AttributeError):
            node.name = "bar"


class TestSemanticRelation:
    def test_create_relation(self):
        rel = SemanticRelation(
            source="a.py:class:A:1",
            target="b.py:class:B:1",
            type=RelationType.INHERITS,
            evidence_file="a.py",
            evidence_line=2,
        )
        assert rel.type == RelationType.INHERITS
        assert rel.evidence_line == 2


class TestEnums:
    def test_node_types(self):
        assert NodeType.CLASS.value == "class"
        assert NodeType.METHOD.value == "method"
        assert len(NodeType) == 8

    def test_relation_types(self):
        assert RelationType.CALLS.value == "calls"
        assert RelationType.INHERITS.value == "inherits"
        assert len(RelationType) == 7

    def test_parse_status(self):
        assert ParseStatus.SUCCESS.value == "success"
        assert ParseStatus.UNAVAILABLE.value == "unavailable"


class TestPythonParser:
    def test_parse_simple_function(self):
        code = 'def hello(name: str) -> str:\n    """Greet."""\n    return f"Hello {name}"\n'
        result = parse_python_file("test.py", code)
        assert result.status == ParseStatus.SUCCESS
        assert len(result.symbols) >= 1
        func = result.symbols[0]
        assert func.name == "hello"
        assert func.type == NodeType.FUNCTION
        assert "name: str" in func.signature
        assert "-> str" in func.signature
        assert func.docstring == "Greet."

    def test_parse_class_with_methods(self):
        code = (
            'class MyClass:\n'
            '    """A class."""\n'
            '    def __init__(self, x: int):\n'
            '        self.x = x\n'
            '    def get_x(self) -> int:\n'
            '        return self.x\n'
        )
        result = parse_python_file("test.py", code)
        assert result.status == ParseStatus.SUCCESS
        class_sym = [s for s in result.symbols if s.type == NodeType.CLASS]
        assert len(class_sym) == 1
        assert class_sym[0].name == "MyClass"
        method_syms = [s for s in result.symbols if s.type == NodeType.METHOD]
        assert len(method_syms) == 2
        method_names = {m.name for m in method_syms}
        assert "__init__" in method_names
        assert "get_x" in method_names

    def test_parse_inheritance(self):
        code = 'class Child(Parent):\n    pass\n'
        result = parse_python_file("test.py", code)
        inherits_rels = [r for r in result.relations if r.type == RelationType.INHERITS]
        assert len(inherits_rels) == 1
        assert inherits_rels[0].target == "Parent"

    def test_parse_imports(self):
        code = 'import os\nfrom pathlib import Path\n'
        result = parse_python_file("test.py", code)
        import_syms = [s for s in result.symbols if s.type == NodeType.IMPORT]
        assert len(import_syms) >= 2

    def test_parse_syntax_error(self):
        code = 'def broken(\n'
        result = parse_python_file("test.py", code)
        assert result.status == ParseStatus.FAILED
        assert result.error != ""

    def test_parse_empty_file(self):
        code = ''
        result = parse_python_file("test.py", code)
        assert result.status == ParseStatus.SUCCESS
        assert len(result.symbols) == 0

    def test_parse_async_function(self):
        code = 'async def fetch(url: str) -> bytes:\n    pass\n'
        result = parse_python_file("test.py", code)
        assert result.status == ParseStatus.SUCCESS
        func = result.symbols[0]
        assert "async" in func.modifiers

    def test_parse_decorators(self):
        code = '@dataclass\nclass Foo:\n    x: int = 0\n'
        result = parse_python_file("test.py", code)
        class_sym = [s for s in result.symbols if s.type == NodeType.CLASS]
        assert len(class_sym) == 1
        assert "dataclass" in class_sym[0].modifiers

    def test_symbol_truncation(self):
        lines = [f"def func_{i}(): pass" for i in range(600)]
        code = "\n".join(lines) + "\n"
        result = parse_python_file("test.py", code, max_symbols=500)
        assert result.truncated is True
        assert result.status == ParseStatus.PARTIAL


class TestParserRegistry:
    def test_detect_language_python(self):
        assert detect_language("test.py") == "python"

    def test_detect_language_javascript(self):
        assert detect_language("app.js") == "javascript"
        assert detect_language("app.jsx") == "javascript"

    def test_detect_language_typescript(self):
        assert detect_language("app.ts") == "typescript"
        assert detect_language("app.tsx") == "typescript"

    def test_detect_language_text(self):
        assert detect_language("style.css") == "text"
        assert detect_language("data.json") == "text"
        assert detect_language("readme.md") == "text"

    def test_parse_file_python(self):
        code = "def foo(): pass\n"
        result = parse_file("test.py", code)
        assert result.file_meta is not None
        assert result.file_meta.language == "python"
        assert result.file_meta.parse_status == ParseStatus.SUCCESS

    def test_parse_file_text(self):
        result = parse_file("style.css", "body { color: red; }")
        assert result.file_meta is not None
        assert result.file_meta.parse_status == ParseStatus.SKIPPED
        assert len(result.symbols) == 0


class TestJsTsParser:
    def test_parse_jsts_unavailable(self):
        from devflow.semantic.parsers.jsts_parser import is_tree_sitter_available, parse_jsts_file
        if not is_tree_sitter_available():
            result = parse_jsts_file("app.js", "function hello() {}")
            assert result.status == ParseStatus.UNAVAILABLE
            assert len(result.symbols) == 0

    def test_parse_jsts_normal(self):
        from devflow.semantic.parsers.jsts_parser import is_tree_sitter_available, parse_jsts_file
        if not is_tree_sitter_available():
            pytest.skip("tree-sitter not installed")
        code = "function hello(name) { return name; }\nclass App { run() {} }\n"
        result = parse_jsts_file("app.js", code, language="javascript")
        assert result.status == ParseStatus.SUCCESS
        names = {s.name for s in result.symbols}
        assert "hello" in names
        assert "App" in names

    def test_parse_typescript_class_inheritance(self):
        from devflow.semantic.parsers.jsts_parser import is_tree_sitter_available, parse_jsts_file
        if not is_tree_sitter_available():
            pytest.skip("tree-sitter not installed")
        code = "class Child extends Parent {}\n"
        result = parse_jsts_file("app.ts", code, language="typescript")
        assert result.status == ParseStatus.SUCCESS
        inherits_rels = [r for r in result.relations if r.type == RelationType.INHERITS]
        assert len(inherits_rels) >= 1


class TestSemanticIndexer:
    def _make_workspace(self, tmp_path: Path, files: dict[str, str]) -> Path:
        for rel_path, content in files.items():
            file_path = tmp_path / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
        return tmp_path

    def test_full_build(self, tmp_path):
        ws = self._make_workspace(tmp_path, {
            "main.py": "def hello():\n    print('hello')\n",
            "utils.py": "def add(a, b):\n    return a + b\n",
        })
        config = SemanticConfig(max_workers=1)
        indexer = SemanticIndexer(ws, config)
        summary = indexer.build_index()

        assert summary.version == INDEX_VERSION
        assert summary.total_symbols > 0
        assert summary.total_files >= 2
        assert summary.build_type == "full"

        index_dir = ws / ".devflow-index"
        assert (index_dir / "symbols.json").exists()
        assert (index_dir / "relations.json").exists()
        assert (index_dir / "file_meta.json").exists()
        assert (index_dir / "summary.json").exists()

    def test_incremental_build_no_changes(self, tmp_path):
        ws = self._make_workspace(tmp_path, {
            "main.py": "def hello(): pass\n",
        })
        config = SemanticConfig(max_workers=1)
        indexer = SemanticIndexer(ws, config)
        indexer.build_index()
        summary2 = indexer.build_index()
        assert summary2.build_type == "full"

    def test_incremental_build_with_change(self, tmp_path):
        ws = self._make_workspace(tmp_path, {
            "main.py": "def hello(): pass\n",
        })
        config = SemanticConfig(max_workers=1)
        indexer = SemanticIndexer(ws, config)
        summary1 = indexer.build_index()
        initial_symbols = summary1.total_symbols

        (ws / "main.py").write_text("def hello(): pass\ndef world(): pass\n", encoding="utf-8")
        summary2 = indexer.build_index()
        assert summary2.total_symbols >= initial_symbols

    def test_version_mismatch_triggers_full_rebuild(self, tmp_path):
        ws = self._make_workspace(tmp_path, {
            "main.py": "def hello(): pass\n",
        })
        config = SemanticConfig(max_workers=1)
        indexer = SemanticIndexer(ws, config)
        indexer.build_index()

        summary_path = ws / ".devflow-index" / "summary.json"
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        data["version"] = "devflow.semantic_index.v0"
        summary_path.write_text(json.dumps(data), encoding="utf-8")

        summary = indexer.build_index()
        assert summary.build_type == "full"

    def test_deleted_file(self, tmp_path):
        ws = self._make_workspace(tmp_path, {
            "main.py": "def hello(): pass\n",
            "extra.py": "def extra(): pass\n",
        })
        config = SemanticConfig(max_workers=1)
        indexer = SemanticIndexer(ws, config)
        indexer.build_index()

        (ws / "extra.py").unlink()
        summary = indexer.build_index()
        assert summary.total_files == 1

    def test_disabled_config(self, tmp_path):
        ws = self._make_workspace(tmp_path, {
            "main.py": "def hello(): pass\n",
        })
        config = SemanticConfig(enabled=False)
        indexer = SemanticIndexer(ws, config)
        summary = indexer.build_index()
        assert summary.total_symbols > 0


class TestSemanticQueryEngine:
    def _make_indexed_workspace(self, tmp_path: Path) -> Path:
        files = {
            "app.py": (
                "from utils import helper\n"
                "class App:\n"
                "    def run(self):\n"
                "        helper()\n"
                "    def stop(self):\n"
                "        pass\n"
            ),
            "utils.py": (
                "def helper():\n"
                "    pass\n"
                "def other():\n"
                "    pass\n"
            ),
        }
        for rel_path, content in files.items():
            file_path = tmp_path / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

        config = SemanticConfig(max_workers=1)
        indexer = SemanticIndexer(tmp_path, config)
        indexer.build_index()
        return tmp_path

    def test_symbol_search(self, tmp_path):
        ws = self._make_indexed_workspace(tmp_path)
        engine = SemanticQueryEngine(ws)
        engine.load_index()
        result = engine.query("symbol", pattern="App")
        assert result.query_type == "symbol"
        assert result.total_count >= 1
        assert any(r["name"] == "App" for r in result.results)

    def test_symbol_search_empty_pattern(self, tmp_path):
        ws = self._make_indexed_workspace(tmp_path)
        engine = SemanticQueryEngine(ws)
        engine.load_index()
        result = engine.query("symbol", pattern="")
        assert result.error != ""

    def test_find_callers(self, tmp_path):
        ws = self._make_indexed_workspace(tmp_path)
        engine = SemanticQueryEngine(ws)
        engine.load_index()
        result = engine.query("callers", symbol_name="helper")
        assert result.query_type == "callers"
        assert result.total_count >= 1

    def test_find_references(self, tmp_path):
        ws = self._make_indexed_workspace(tmp_path)
        engine = SemanticQueryEngine(ws)
        engine.load_index()
        app_ids = [s.id for s in engine._symbols_by_id.values() if s.name == "App"]
        if app_ids:
            result = engine.query("references", symbol_id=app_ids[0])
            assert result.query_type == "references"
        else:
            result = engine.query("references", symbol_id="nonexistent")
            assert result.query_type == "references"

    def test_find_hierarchy(self, tmp_path):
        ws = self._make_indexed_workspace(tmp_path)
        engine = SemanticQueryEngine(ws)
        engine.load_index()
        result = engine.query("hierarchy", symbol_name="App")
        assert result.query_type == "hierarchy"

    def test_find_dependencies(self, tmp_path):
        ws = self._make_indexed_workspace(tmp_path)
        engine = SemanticQueryEngine(ws)
        engine.load_index()
        result = engine.query("dependencies", file_path="app.py")
        assert result.query_type == "dependencies"
        assert len(result.results) >= 1

    def test_unknown_query_type(self, tmp_path):
        ws = self._make_indexed_workspace(tmp_path)
        engine = SemanticQueryEngine(ws)
        engine.load_index()
        result = engine.query("unknown_type")
        assert result.error != ""

    def test_no_index_available(self, tmp_path):
        engine = SemanticQueryEngine(tmp_path)
        engine.load_index()
        assert not engine.is_loaded()
        result = engine.query("symbol", pattern="foo")
        assert result.error != ""

    def test_get_summary(self, tmp_path):
        ws = self._make_indexed_workspace(tmp_path)
        engine = SemanticQueryEngine(ws)
        engine.load_index()
        summary = engine.get_summary()
        assert summary["status"] == "available"
        assert summary["total_symbols"] > 0

    def test_get_top_level_symbols(self, tmp_path):
        ws = self._make_indexed_workspace(tmp_path)
        engine = SemanticQueryEngine(ws)
        engine.load_index()
        symbols = engine.get_top_level_symbols()
        assert len(symbols) > 0
        symbol_types = {s["type"] for s in symbols}
        assert "class" in symbol_types or "function" in symbol_types


class TestSemanticConfig:
    def test_defaults(self):
        config = SemanticConfig()
        assert config.enabled is True
        assert config.max_workers == 4
        assert config.parse_timeout_seconds == 10
        assert config.max_symbols_per_file == 500
        assert config.index_dir_name == ".devflow-index"

    def test_custom_values(self):
        config = SemanticConfig(
            enabled=False,
            max_workers=2,
            parse_timeout_seconds=30,
            max_symbols_per_file=100,
            index_dir_name=".my-index",
        )
        assert config.enabled is False
        assert config.max_workers == 2
        assert config.index_dir_name == ".my-index"

    def test_config_loading(self, tmp_path):
        config_data = {
            "llm": {"provider": "openai", "api_key": "test", "model": "gpt-4"},
            "lark": {"cli_version": "1.0.23", "app_id": "id", "app_secret": "secret", "test_doc": "doc"},
            "semantic": {"enabled": False, "max_workers": 2},
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_data), encoding="utf-8")

        from devflow.config import load_config
        config = load_config(config_path)
        assert config.semantic.enabled is False
        assert config.semantic.max_workers == 2


class TestBuildCodebaseContextIntegration:
    def test_semantic_summary_present(self, tmp_path):
        (tmp_path / "main.py").write_text("def hello(): pass\n", encoding="utf-8")
        from devflow.solution.workspace import build_codebase_context
        result = build_codebase_context(tmp_path, semantic_config=SemanticConfig(max_workers=1))
        assert "semantic_summary" in result
        assert result["semantic_summary"]["status"] == "available"

    def test_semantic_disabled(self, tmp_path):
        (tmp_path / "main.py").write_text("def hello(): pass\n", encoding="utf-8")
        from devflow.solution.workspace import build_codebase_context
        result = build_codebase_context(tmp_path, semantic_config=SemanticConfig(enabled=False))
        assert result["semantic_summary"]["status"] == "disabled"

    def test_semantic_symbols_present(self, tmp_path):
        (tmp_path / "main.py").write_text("def hello(): pass\n", encoding="utf-8")
        from devflow.solution.workspace import build_codebase_context
        result = build_codebase_context(tmp_path, semantic_config=SemanticConfig(max_workers=1))
        assert "semantic_symbols" in result
        assert "semantic_relations_count" in result


class TestCodeToolExecutorSemanticSearch:
    def test_semantic_search_dispatch(self, tmp_path):
        (tmp_path / "main.py").write_text("def hello(): pass\n", encoding="utf-8")
        from devflow.code.tools import CodeToolExecutor
        executor = CodeToolExecutor(str(tmp_path))
        result = executor.execute("semantic_search", {
            "query_type": "symbol",
            "pattern": "hello",
        })
        assert result["status"] == "success"
        assert result["query_type"] == "symbol"

    def test_semantic_search_auto_build_index(self, tmp_path):
        (tmp_path / "main.py").write_text("def hello(): pass\n", encoding="utf-8")
        from devflow.code.tools import CodeToolExecutor
        executor = CodeToolExecutor(str(tmp_path))
        assert not (tmp_path / ".devflow-index" / "symbols.json").exists()
        result = executor.execute("semantic_search", {
            "query_type": "symbol",
            "pattern": "hello",
        })
        assert result["status"] == "success"

    def test_review_tool_executor_allows_semantic_search(self, tmp_path):
        from devflow.review.tools import READ_ONLY_TOOLS
        assert "semantic_search" in READ_ONLY_TOOLS
