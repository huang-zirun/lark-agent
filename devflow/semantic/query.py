from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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


MAX_QUERY_RESULTS = 50


@dataclass(slots=True)
class QueryResult:
    results: list[dict[str, Any]] = field(default_factory=list)
    total_count: int = 0
    truncated: bool = False
    query_type: str = ""
    error: str = ""


class SemanticQueryEngine:

    def __init__(self, workspace_root: Path | str) -> None:
        self.root = Path(workspace_root).expanduser().resolve()
        self._symbols_by_id: dict[str, SemanticNode] = {}
        self._symbols_by_name: dict[str, list[str]] = {}
        self._symbols_by_file: dict[str, list[str]] = {}
        self._relations_by_source: dict[str, list[SemanticRelation]] = {}
        self._relations_by_target: dict[str, list[SemanticRelation]] = {}
        self._loaded: bool = False

    def load_index(self) -> None:
        if self._loaded:
            return

        from devflow.semantic.indexer import SemanticIndexer
        indexer = SemanticIndexer(self.root)

        if not indexer._index_exists():
            return

        symbols = indexer._load_symbols()
        relations = indexer._load_relations()

        self._symbols_by_id.clear()
        self._symbols_by_name.clear()
        self._symbols_by_file.clear()
        self._relations_by_source.clear()
        self._relations_by_target.clear()

        for sym in symbols:
            self._symbols_by_id[sym.id] = sym
            self._symbols_by_name.setdefault(sym.name, []).append(sym.id)
            self._symbols_by_file.setdefault(sym.file_path, []).append(sym.id)

        for rel in relations:
            self._relations_by_source.setdefault(rel.source, []).append(rel)
            self._relations_by_target.setdefault(rel.target, []).append(rel)

        self._loaded = True

    def is_loaded(self) -> bool:
        return self._loaded

    def query(self, query_type: str, **kwargs: Any) -> QueryResult:
        if not self._loaded:
            self.load_index()

        if not self._loaded:
            return QueryResult(query_type=query_type, error="索引不可用")

        if query_type == "symbol":
            return self._symbol_search(kwargs.get("pattern", ""))
        elif query_type == "references":
            return self._find_references(kwargs.get("symbol_id", ""))
        elif query_type == "callers":
            return self._find_callers(kwargs.get("symbol_name", ""))
        elif query_type == "hierarchy":
            return self._find_hierarchy(kwargs.get("symbol_name", ""))
        elif query_type == "dependencies":
            return self._find_dependencies(kwargs.get("file_path", ""))
        else:
            return QueryResult(query_type=query_type, error=f"未知查询类型：{query_type}")

    def _symbol_search(self, pattern: str) -> QueryResult:
        if not pattern:
            return QueryResult(query_type="symbol", error="pattern 不能为空")

        pattern_lower = pattern.lower()
        matches: list[SemanticNode] = []

        for name, ids in self._symbols_by_name.items():
            if pattern_lower in name.lower():
                for sid in ids:
                    sym = self._symbols_by_id.get(sid)
                    if sym is not None:
                        matches.append(sym)

        total = len(matches)
        truncated = total > MAX_QUERY_RESULTS
        results = [_symbol_to_dict(s) for s in matches[:MAX_QUERY_RESULTS]]

        return QueryResult(
            results=results,
            total_count=total,
            truncated=truncated,
            query_type="symbol",
        )

    def _find_references(self, symbol_id: str) -> QueryResult:
        if not symbol_id:
            return QueryResult(query_type="references", error="symbol_id 不能为空")

        sym = self._symbols_by_id.get(symbol_id)
        if sym is None:
            return QueryResult(query_type="references", error=f"未找到符号：{symbol_id}")

        refs: list[dict[str, Any]] = []

        for rel in self._relations_by_target.get(symbol_id, []):
            source_sym = self._symbols_by_id.get(rel.source)
            refs.append({
                "source_id": rel.source,
                "source_name": source_sym.name if source_sym else rel.source,
                "source_file": source_sym.file_path if source_sym else rel.evidence_file,
                "source_line": source_sym.line_start if source_sym else rel.evidence_line,
                "relation_type": rel.type.value,
                "evidence_file": rel.evidence_file,
                "evidence_line": rel.evidence_line,
            })

        for rel in self._relations_by_target.get(sym.name, []):
            source_sym = self._symbols_by_id.get(rel.source)
            ref_entry = {
                "source_id": rel.source,
                "source_name": source_sym.name if source_sym else rel.source,
                "source_file": source_sym.file_path if source_sym else rel.evidence_file,
                "source_line": source_sym.line_start if source_sym else rel.evidence_line,
                "relation_type": rel.type.value,
                "evidence_file": rel.evidence_file,
                "evidence_line": rel.evidence_line,
            }
            if ref_entry not in refs:
                refs.append(ref_entry)

        total = len(refs)
        truncated = total > MAX_QUERY_RESULTS
        return QueryResult(
            results=refs[:MAX_QUERY_RESULTS],
            total_count=total,
            truncated=truncated,
            query_type="references",
        )

    def _find_callers(self, symbol_name: str) -> QueryResult:
        if not symbol_name:
            return QueryResult(query_type="callers", error="symbol_name 不能为空")

        callers: list[dict[str, Any]] = []
        seen_sources: set[str] = set()

        for rel in self._relations_by_target.get(symbol_name, []):
            if rel.type != RelationType.CALLS:
                continue
            if rel.source in seen_sources:
                continue
            seen_sources.add(rel.source)
            source_sym = self._symbols_by_id.get(rel.source)
            callers.append({
                "caller_id": rel.source,
                "caller_name": source_sym.name if source_sym else rel.source,
                "caller_file": source_sym.file_path if source_sym else rel.evidence_file,
                "caller_line": source_sym.line_start if source_sym else rel.evidence_line,
                "call_site_file": rel.evidence_file,
                "call_site_line": rel.evidence_line,
            })

        for name_key in [symbol_name, f"*.{symbol_name}"]:
            for rel in self._relations_by_target.get(name_key, []):
                if rel.type != RelationType.CALLS:
                    continue
                if rel.source in seen_sources:
                    continue
                seen_sources.add(rel.source)
                source_sym = self._symbols_by_id.get(rel.source)
                callers.append({
                    "caller_id": rel.source,
                    "caller_name": source_sym.name if source_sym else rel.source,
                    "caller_file": source_sym.file_path if source_sym else rel.evidence_file,
                    "caller_line": source_sym.line_start if source_sym else rel.evidence_line,
                    "call_site_file": rel.evidence_file,
                    "call_site_line": rel.evidence_line,
                })

        total = len(callers)
        truncated = total > MAX_QUERY_RESULTS
        return QueryResult(
            results=callers[:MAX_QUERY_RESULTS],
            total_count=total,
            truncated=truncated,
            query_type="callers",
        )

    def _find_hierarchy(self, symbol_name: str) -> QueryResult:
        if not symbol_name:
            return QueryResult(query_type="hierarchy", error="symbol_name 不能为空")

        class_ids = self._symbols_by_name.get(symbol_name, [])
        class_symbols = [self._symbols_by_id[cid] for cid in class_ids if self._symbols_by_id.get(cid, None) and self._symbols_by_id[cid].type == NodeType.CLASS]

        if not class_symbols:
            return QueryResult(query_type="hierarchy", error=f"未找到类：{symbol_name}")

        parents: list[dict[str, Any]] = []
        children: list[dict[str, Any]] = []

        for class_sym in class_symbols:
            for rel in self._relations_by_source.get(class_sym.id, []):
                if rel.type == RelationType.INHERITS:
                    parent_sym = self._symbols_by_id.get(rel.target)
                    parents.append({
                        "name": rel.target,
                        "id": rel.target,
                        "qualified_name": parent_sym.qualified_name if parent_sym else rel.target,
                        "file_path": parent_sym.file_path if parent_sym else "",
                    })

            for rel in self._relations_by_target.get(class_sym.id, []):
                if rel.type == RelationType.INHERITS:
                    child_sym = self._symbols_by_id.get(rel.source)
                    children.append({
                        "name": child_sym.name if child_sym else rel.source,
                        "id": rel.source,
                        "qualified_name": child_sym.qualified_name if child_sym else "",
                        "file_path": child_sym.file_path if child_sym else "",
                    })

            for rel in self._relations_by_target.get(class_sym.name, []):
                if rel.type == RelationType.INHERITS:
                    child_sym = self._symbols_by_id.get(rel.source)
                    entry = {
                        "name": child_sym.name if child_sym else rel.source,
                        "id": rel.source,
                        "qualified_name": child_sym.qualified_name if child_sym else "",
                        "file_path": child_sym.file_path if child_sym else "",
                    }
                    if entry not in children:
                        children.append(entry)

        results = [{"class": _symbol_to_dict(class_sym), "parents": parents, "children": children} for class_sym in class_symbols[:MAX_QUERY_RESULTS]]
        return QueryResult(
            results=results,
            total_count=len(results),
            truncated=len(results) > MAX_QUERY_RESULTS,
            query_type="hierarchy",
        )

    def _find_dependencies(self, file_path: str) -> QueryResult:
        if not file_path:
            return QueryResult(query_type="dependencies", error="file_path 不能为空")

        imports: list[dict[str, Any]] = []
        imported_by: list[dict[str, Any]] = []

        file_symbol_ids = self._symbols_by_file.get(file_path, [])
        for sid in file_symbol_ids:
            for rel in self._relations_by_source.get(sid, []):
                if rel.type == RelationType.IMPORTS:
                    target_sym = self._symbols_by_id.get(rel.target)
                    imports.append({
                        "target": rel.target,
                        "target_name": target_sym.name if target_sym else rel.target,
                        "target_file": target_sym.file_path if target_sym else "",
                        "evidence_line": rel.evidence_line,
                    })

        module_name = file_path.replace("/", ".").removesuffix(".py").removesuffix(".js").removesuffix(".ts")
        for target_key in [file_path, module_name]:
            for rel in self._relations_by_target.get(target_key, []):
                if rel.type == RelationType.IMPORTS:
                    source_sym = self._symbols_by_id.get(rel.source)
                    imported_by.append({
                        "source_id": rel.source,
                        "source_name": source_sym.name if source_sym else rel.source,
                        "source_file": source_sym.file_path if source_sym else rel.evidence_file,
                        "evidence_line": rel.evidence_line,
                    })

        seen: set[str] = set()
        unique_imported_by: list[dict[str, Any]] = []
        for entry in imported_by:
            key = f"{entry.get('source_id', '')}:{entry.get('source_file', '')}"
            if key not in seen:
                seen.add(key)
                unique_imported_by.append(entry)

        return QueryResult(
            results=[{
                "file_path": file_path,
                "imports": imports[:MAX_QUERY_RESULTS],
                "imported_by": unique_imported_by[:MAX_QUERY_RESULTS],
            }],
            total_count=1,
            query_type="dependencies",
        )

    def get_summary(self) -> dict[str, Any]:
        if not self._loaded:
            self.load_index()
        if not self._loaded:
            return {"status": "unavailable"}

        rel_counts: dict[str, int] = {}
        for rels in self._relations_by_source.values():
            for rel in rels:
                key = rel.type.value
                rel_counts[key] = rel_counts.get(key, 0) + 1

        return {
            "status": "available",
            "total_symbols": len(self._symbols_by_id),
            "total_relations": sum(len(r) for r in self._relations_by_source.values()),
            "relation_type_counts": rel_counts,
        }

    def get_top_level_symbols(self, file_path: str | None = None) -> list[dict[str, Any]]:
        if not self._loaded:
            self.load_index()
        if not self._loaded:
            return []

        top_types = {NodeType.CLASS, NodeType.FUNCTION, NodeType.IMPORT}
        results: list[dict[str, Any]] = []

        if file_path:
            ids = self._symbols_by_file.get(file_path, [])
            for sid in ids:
                sym = self._symbols_by_id.get(sid)
                if sym and sym.type in top_types:
                    results.append(_symbol_to_dict(sym))
        else:
            for sym in self._symbols_by_id.values():
                if sym.type in top_types:
                    results.append(_symbol_to_dict(sym))

        return results[:200]


def _symbol_to_dict(sym: SemanticNode) -> dict[str, Any]:
    return {
        "id": sym.id,
        "type": sym.type.value,
        "name": sym.name,
        "qualified_name": sym.qualified_name,
        "file_path": sym.file_path,
        "line_start": sym.line_start,
        "line_end": sym.line_end,
        "signature": sym.signature,
        "docstring": sym.docstring,
        "modifiers": list(sym.modifiers),
    }
