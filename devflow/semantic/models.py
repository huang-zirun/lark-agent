from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class NodeType(enum.Enum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    IMPORT = "import"
    PARAMETER = "parameter"
    DECORATOR = "decorator"


class RelationType(enum.Enum):
    CONTAINS = "contains"
    IMPORTS = "imports"
    CALLS = "calls"
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    REFERENCES = "references"
    DECORATES = "decorates"


class ParseStatus(enum.Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class SemanticNode:
    id: str
    type: NodeType
    name: str
    qualified_name: str
    file_path: str
    line_start: int
    line_end: int
    signature: str = ""
    docstring: str = ""
    modifiers: tuple[str, ...] = ()
    children: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SemanticRelation:
    source: str
    target: str
    type: RelationType
    evidence_file: str = ""
    evidence_line: int = 0


@dataclass(frozen=True, slots=True)
class FileMeta:
    path: str
    hash: str
    language: str
    line_count: int
    parse_status: ParseStatus
    parse_error: str = ""
    symbol_count: int = 0
    last_indexed_at: str = ""
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class IndexSummary:
    version: str
    total_symbols: int
    total_relations: int
    total_files: int
    language_distribution: dict[str, int] = field(default_factory=dict)
    relation_type_counts: dict[str, int] = field(default_factory=dict)
    build_time_ms: int = 0
    build_type: str = "full"


INDEX_VERSION = "devflow.semantic_index.v1"
