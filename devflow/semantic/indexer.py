from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import time
from pathlib import Path

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
from devflow.semantic.parsers import EXCLUDED_DIRECTORIES, FileParseResult, parse_file


class SemanticIndexer:
    def __init__(self, workspace_root: Path | str, config: SemanticConfig | None = None) -> None:
        self.root = Path(workspace_root).expanduser().resolve()
        self.config = config or SemanticConfig()
        self.index_dir = self.root / self.config.index_dir_name

    def build_index(self, *, force_full: bool = False) -> IndexSummary:
        if force_full or not self._index_exists() or not self._version_matches():
            return self._full_build()
        return self._incremental_build()

    def _index_exists(self) -> bool:
        return (self.index_dir / "summary.json").exists() and (self.index_dir / "symbols.json").exists()

    def _version_matches(self) -> bool:
        try:
            summary = self._load_summary()
            return summary.version == INDEX_VERSION
        except (OSError, json.JSONDecodeError, KeyError):
            return False

    def _full_build(self) -> IndexSummary:
        start_time = time.monotonic()

        files = self._collect_files()

        parse_results = self._parse_files(files)

        all_symbols, all_relations, file_metas = self._aggregate_results(parse_results)

        self._write_index(all_symbols, all_relations, file_metas)

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        summary = self._build_summary(all_symbols, all_relations, file_metas, elapsed_ms, "full")
        self._write_summary(summary)
        return summary

    def _incremental_build(self) -> IndexSummary:
        start_time = time.monotonic()

        existing_symbols, existing_relations, existing_metas = self._load_existing_index()

        current_files = self._collect_files()

        changed, added, deleted, unchanged = self._detect_changes(current_files, existing_metas)

        if not changed and not added and not deleted:
            summary = self._load_summary()
            return summary

        files_to_parse = changed | added
        parse_results = self._parse_files(files_to_parse)

        files_to_remove = changed | deleted
        remaining_symbols = [s for s in existing_symbols if s.file_path not in files_to_remove]
        remaining_relations = [r for r in existing_relations if r.evidence_file not in files_to_remove]
        remaining_metas = {p: m for p, m in existing_metas.items() if p not in files_to_remove}

        new_symbols, new_relations, new_metas = self._aggregate_results(parse_results)
        all_symbols = remaining_symbols + new_symbols
        all_relations = remaining_relations + new_relations
        all_metas = {**remaining_metas, **new_metas}

        self._write_index(all_symbols, all_relations, all_metas)

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        summary = self._build_summary(all_symbols, all_relations, all_metas, elapsed_ms, "incremental")
        self._write_summary(summary)
        return summary

    def _collect_files(self) -> set[str]:
        files: set[str] = set()
        index_dir_name = self.config.index_dir_name
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [
                d
                for d in dirnames
                if d not in EXCLUDED_DIRECTORIES and not d.startswith(".") and d != index_dir_name
            ]
            for fname in filenames:
                full_path = Path(dirpath) / fname
                try:
                    rel = full_path.relative_to(self.root).as_posix()
                except ValueError:
                    continue
                files.add(rel)
        return files

    def _parse_files(self, file_paths: set[str]) -> list[FileParseResult]:
        results: list[FileParseResult] = []
        max_workers = self.config.max_workers

        if max_workers > 1 and len(file_paths) > 10:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {}
                for fp in file_paths:
                    full_path = self.root / fp
                    try:
                        content = full_path.read_text(encoding="utf-8")
                    except (OSError, UnicodeDecodeError):
                        continue
                    if full_path.stat().st_size > 1024 * 1024:
                        continue
                    futures[
                        executor.submit(
                            parse_file,
                            fp,
                            content,
                            self.config.max_symbols_per_file,
                            self.config.parse_timeout_seconds,
                        )
                    ] = fp

                for future in concurrent.futures.as_completed(
                    futures, timeout=self.config.parse_timeout_seconds * len(futures)
                ):
                    try:
                        results.append(future.result(timeout=self.config.parse_timeout_seconds))
                    except Exception:
                        fp = futures[future]
                        results.append(FileParseResult(file_path=fp, error="parse timeout"))
        else:
            for fp in file_paths:
                full_path = self.root / fp
                try:
                    content = full_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                if full_path.stat().st_size > 1024 * 1024:
                    continue
                try:
                    result = parse_file(
                        fp, content, self.config.max_symbols_per_file, self.config.parse_timeout_seconds
                    )
                    results.append(result)
                except Exception as exc:
                    results.append(FileParseResult(file_path=fp, error=str(exc)))

        return results

    def _detect_changes(
        self, current_files: set[str], existing_metas: dict[str, FileMeta]
    ) -> tuple[set[str], set[str], set[str], set[str]]:
        existing_paths = set(existing_metas.keys())
        added = current_files - existing_paths
        deleted = existing_paths - current_files
        changed: set[str] = set()
        unchanged: set[str] = set()

        for fp in current_files & existing_paths:
            full_path = self.root / fp
            try:
                content = full_path.read_text(encoding="utf-8")
                current_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            except (OSError, UnicodeDecodeError):
                changed.add(fp)
                continue
            if current_hash != existing_metas[fp].hash:
                changed.add(fp)
            else:
                unchanged.add(fp)

        return changed, added, deleted, unchanged

    def _aggregate_results(
        self, results: list[FileParseResult]
    ) -> tuple[list[SemanticNode], list[SemanticRelation], dict[str, FileMeta]]:
        all_symbols: list[SemanticNode] = []
        all_relations: list[SemanticRelation] = []
        all_metas: dict[str, FileMeta] = {}

        for result in results:
            all_symbols.extend(result.symbols)
            all_relations.extend(result.relations)
            if result.file_meta is not None:
                all_metas[result.file_path] = result.file_meta

        return all_symbols, all_relations, all_metas

    def _write_index(
        self,
        symbols: list[SemanticNode],
        relations: list[SemanticRelation],
        metas: dict[str, FileMeta],
    ) -> None:
        self.index_dir.mkdir(parents=True, exist_ok=True)

        symbols_data = self._symbols_to_json(symbols)
        relations_data = self._relations_to_json(relations)
        metas_data = self._metas_to_json(metas)

        self._atomic_write_json(self.index_dir / "symbols.json", symbols_data)
        self._atomic_write_json(self.index_dir / "relations.json", relations_data)
        self._atomic_write_json(self.index_dir / "file_meta.json", metas_data)

    def _write_summary(self, summary: IndexSummary) -> None:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._atomic_write_json(self.index_dir / "summary.json", self._summary_to_json(summary))

    def _atomic_write_json(self, path: Path, data: dict | list) -> None:
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(path)

    def _load_existing_index(
        self,
    ) -> tuple[list[SemanticNode], list[SemanticRelation], dict[str, FileMeta]]:
        symbols = self._load_symbols()
        relations = self._load_relations()
        metas = self._load_metas()
        return symbols, relations, metas

    def _load_summary(self) -> IndexSummary:
        data = json.loads((self.index_dir / "summary.json").read_text(encoding="utf-8"))
        return IndexSummary(
            version=data["version"],
            total_symbols=data["total_symbols"],
            total_relations=data["total_relations"],
            total_files=data["total_files"],
            language_distribution=data.get("language_distribution", {}),
            relation_type_counts=data.get("relation_type_counts", {}),
            build_time_ms=data.get("build_time_ms", 0),
            build_type=data.get("build_type", "full"),
        )

    def _load_symbols(self) -> list[SemanticNode]:
        if not (self.index_dir / "symbols.json").exists():
            return []
        data = json.loads((self.index_dir / "symbols.json").read_text(encoding="utf-8"))
        return self._json_to_symbols(data)

    def _load_relations(self) -> list[SemanticRelation]:
        if not (self.index_dir / "relations.json").exists():
            return []
        data = json.loads((self.index_dir / "relations.json").read_text(encoding="utf-8"))
        return self._json_to_relations(data)

    def _load_metas(self) -> dict[str, FileMeta]:
        if not (self.index_dir / "file_meta.json").exists():
            return {}
        data = json.loads((self.index_dir / "file_meta.json").read_text(encoding="utf-8"))
        return self._json_to_metas(data)

    def _symbols_to_json(self, symbols: list[SemanticNode]) -> dict:
        files_dict: dict[str, dict] = {}
        for sym in symbols:
            fp = sym.file_path
            if fp not in files_dict:
                files_dict[fp] = {"symbols": []}
            files_dict[fp]["symbols"].append(
                {
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
                    "children": list(sym.children),
                }
            )
        return {"version": INDEX_VERSION, "files": files_dict}

    def _relations_to_json(self, relations: list[SemanticRelation]) -> dict:
        edges = []
        for rel in relations:
            edges.append(
                {
                    "source": rel.source,
                    "target": rel.target,
                    "type": rel.type.value,
                    "evidence_file": rel.evidence_file,
                    "evidence_line": rel.evidence_line,
                }
            )
        return {"version": INDEX_VERSION, "edges": edges}

    def _metas_to_json(self, metas: dict[str, FileMeta]) -> dict:
        files = {}
        for path, meta in metas.items():
            files[path] = {
                "path": meta.path,
                "hash": meta.hash,
                "language": meta.language,
                "line_count": meta.line_count,
                "parse_status": meta.parse_status.value,
                "parse_error": meta.parse_error,
                "symbol_count": meta.symbol_count,
                "last_indexed_at": meta.last_indexed_at,
                "truncated": meta.truncated,
            }
        return {"version": INDEX_VERSION, "files": files}

    def _summary_to_json(self, summary: IndexSummary) -> dict:
        return {
            "version": summary.version,
            "total_symbols": summary.total_symbols,
            "total_relations": summary.total_relations,
            "total_files": summary.total_files,
            "language_distribution": summary.language_distribution,
            "relation_type_counts": summary.relation_type_counts,
            "build_time_ms": summary.build_time_ms,
            "build_type": summary.build_type,
        }

    def _json_to_symbols(self, data: dict) -> list[SemanticNode]:
        symbols = []
        for fp, file_data in data.get("files", {}).items():
            for sym_data in file_data.get("symbols", []):
                symbols.append(
                    SemanticNode(
                        id=sym_data["id"],
                        type=NodeType(sym_data["type"]),
                        name=sym_data["name"],
                        qualified_name=sym_data["qualified_name"],
                        file_path=sym_data["file_path"],
                        line_start=sym_data["line_start"],
                        line_end=sym_data["line_end"],
                        signature=sym_data.get("signature", ""),
                        docstring=sym_data.get("docstring", ""),
                        modifiers=tuple(sym_data.get("modifiers", [])),
                        children=tuple(sym_data.get("children", [])),
                    )
                )
        return symbols

    def _json_to_relations(self, data: dict) -> list[SemanticRelation]:
        relations = []
        for edge_data in data.get("edges", []):
            relations.append(
                SemanticRelation(
                    source=edge_data["source"],
                    target=edge_data["target"],
                    type=RelationType(edge_data["type"]),
                    evidence_file=edge_data.get("evidence_file", ""),
                    evidence_line=edge_data.get("evidence_line", 0),
                )
            )
        return relations

    def _json_to_metas(self, data: dict) -> dict[str, FileMeta]:
        metas = {}
        for path, meta_data in data.get("files", {}).items():
            metas[path] = FileMeta(
                path=meta_data["path"],
                hash=meta_data["hash"],
                language=meta_data["language"],
                line_count=meta_data["line_count"],
                parse_status=ParseStatus(meta_data["parse_status"]),
                parse_error=meta_data.get("parse_error", ""),
                symbol_count=meta_data.get("symbol_count", 0),
                last_indexed_at=meta_data.get("last_indexed_at", ""),
                truncated=meta_data.get("truncated", False),
            )
        return metas

    def _build_summary(
        self, symbols, relations, metas, elapsed_ms, build_type
    ) -> IndexSummary:
        lang_dist: dict[str, int] = {}
        rel_counts: dict[str, int] = {}
        for meta in metas.values():
            lang_dist[meta.language] = lang_dist.get(meta.language, 0) + 1
        for rel in relations:
            key = rel.type.value
            rel_counts[key] = rel_counts.get(key, 0) + 1
        return IndexSummary(
            version=INDEX_VERSION,
            total_symbols=len(symbols),
            total_relations=len(relations),
            total_files=len(metas),
            language_distribution=lang_dist,
            relation_type_counts=rel_counts,
            build_time_ms=elapsed_ms,
            build_type=build_type,
        )
