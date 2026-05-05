from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterator

from devflow.semantic.models import (
    NodeType,
    ParseStatus,
    RelationType,
    SemanticNode,
    SemanticRelation,
)

_ts_available: bool | None = None


def is_tree_sitter_available() -> bool:
    global _ts_available
    if _ts_available is not None:
        return _ts_available
    try:
        import tree_sitter  # noqa: F401

        _ts_available = True
    except ImportError:
        _ts_available = False
    return _ts_available


@dataclass(slots=True)
class ParseResult:
    symbols: list[SemanticNode]
    relations: list[SemanticRelation]
    status: ParseStatus
    error: str = ""


def _get_language(language: str):
    if language in ("typescript", "tsx"):
        try:
            import tree_sitter_typescript as tstypescript

            ts_lang = (
                tstypescript.language_typescript()
                if language == "typescript"
                else tstypescript.language_tsx()
            )
            return ts_lang
        except ImportError:
            return None
    else:
        try:
            import tree_sitter_javascript as tsjs

            return tsjs.language()
        except ImportError:
            return None


def _walk_tree(node) -> Iterator:
    yield node
    for child in node.children:
        yield from _walk_tree(child)


def _resolve_language(file_path: str, language: str) -> str:
    if language != "javascript":
        return language
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".ts", ".tsx"):
        return "tsx" if ext == ".tsx" else "typescript"
    return language


def _make_qualified_name(file_path: str) -> str:
    p = file_path.replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    for ext in (".tsx", ".ts", ".jsx", ".js", ".mjs", ".cjs"):
        if p.endswith(ext):
            p = p[: -len(ext)]
            break
    return p


def _node_text(node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _child_by_type(node, type_name: str):
    for child in node.children:
        if child.type == type_name:
            return child
    return None


def _children_by_type(node, type_name: str) -> list:
    return [c for c in node.children if c.type == type_name]


class JsTsVisitor:
    def __init__(self, file_path: str, module_qualified_name: str, tree) -> None:
        self.file_path = file_path.replace("\\", "/")
        self.module_qualified_name = module_qualified_name
        self.tree = tree
        self.symbols: list[SemanticNode] = []
        self.relations: list[SemanticRelation] = []
        self._source: bytes = b""
        self._id_counter: int = 0

    def _next_id(self) -> str:
        self._id_counter += 1
        return f"{self.module_qualified_name}::{self._id_counter}"

    def _qname(self, name: str) -> str:
        return f"{self.module_qualified_name}.{name}"

    def visit(self, source: bytes) -> None:
        self._source = source
        root = self.tree.root_node
        module_id = self._next_id()
        module_node = SemanticNode(
            id=module_id,
            type=NodeType.MODULE,
            name=self.module_qualified_name.split("/")[-1],
            qualified_name=self.module_qualified_name,
            file_path=self.file_path,
            line_start=root.start_point[0] + 1,
            line_end=root.end_point[0] + 1,
        )
        self.symbols.append(module_node)
        for node in _walk_tree(root):
            handler = getattr(self, f"_handle_{node.type}", None)
            if handler is not None:
                handler(node, module_id)

    def _add_contains(self, parent_id: str, child_id: str, line: int = 0) -> None:
        self.relations.append(
            SemanticRelation(
                source=parent_id,
                target=child_id,
                type=RelationType.CONTAINS,
                evidence_file=self.file_path,
                evidence_line=line,
            )
        )

    def _handle_function_declaration(self, node, parent_id: str) -> None:
        name_node = _child_by_type(node, "identifier")
        if name_node is None:
            return
        name = _node_text(name_node, self._source)
        params_node = _child_by_type(node, "formal_parameters")
        params = ""
        if params_node is not None:
            params = _node_text(params_node, self._source)
        signature = f"function {name}{params}"
        fid = self._next_id()
        sym = SemanticNode(
            id=fid,
            type=NodeType.FUNCTION,
            name=name,
            qualified_name=self._qname(name),
            file_path=self.file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=signature,
        )
        self.symbols.append(sym)
        self._add_contains(parent_id, fid, node.start_point[0] + 1)
        if params_node is not None:
            self._extract_params(params_node, fid)

    def _handle_function_expression(self, node, parent_id: str) -> None:
        name = None
        parent_var = node.parent
        if parent_var is not None and parent_var.type == "variable_declarator":
            var_name_node = _child_by_type(parent_var, "identifier")
            if var_name_node is not None:
                name = _node_text(var_name_node, self._source)
        if name is None:
            name_node = _child_by_type(node, "identifier")
            if name_node is not None:
                name = _node_text(name_node, self._source)
        if name is None:
            return
        params_node = _child_by_type(node, "formal_parameters")
        params = ""
        if params_node is not None:
            params = _node_text(params_node, self._source)
        signature = f"{name}{params}"
        fid = self._next_id()
        sym = SemanticNode(
            id=fid,
            type=NodeType.FUNCTION,
            name=name,
            qualified_name=self._qname(name),
            file_path=self.file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=signature,
        )
        self.symbols.append(sym)
        self._add_contains(parent_id, fid, node.start_point[0] + 1)
        if params_node is not None:
            self._extract_params(params_node, fid)

    def _handle_arrow_function(self, node, parent_id: str) -> None:
        name = None
        parent_var = node.parent
        if parent_var is not None and parent_var.type == "variable_declarator":
            var_name_node = _child_by_type(parent_var, "identifier")
            if var_name_node is not None:
                name = _node_text(var_name_node, self._source)
        if name is None:
            return
        params_node = _child_by_type(node, "formal_parameters")
        params = ""
        if params_node is not None:
            params = _node_text(params_node, self._source)
        else:
            first_child = node.children[0] if node.children else None
            if first_child is not None and first_child.type == "identifier":
                params = _node_text(first_child, self._source)
        signature = f"{name} = {params} =>"
        fid = self._next_id()
        sym = SemanticNode(
            id=fid,
            type=NodeType.FUNCTION,
            name=name,
            qualified_name=self._qname(name),
            file_path=self.file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=signature,
        )
        self.symbols.append(sym)
        self._add_contains(parent_id, fid, node.start_point[0] + 1)
        if params_node is not None:
            self._extract_params(params_node, fid)

    def _handle_class_declaration(self, node, parent_id: str) -> None:
        name_node = _child_by_type(node, "identifier")
        if name_node is None:
            return
        name = _node_text(name_node, self._source)
        modifiers: list[str] = []
        heritage = _child_by_type(node, "class_heritage")
        if heritage is not None:
            for child in heritage.children:
                if child.type == "extends_clause":
                    ext_target = child.child_by_field_name("value")
                    if ext_target is None:
                        for sc in child.children:
                            if sc.type in ("identifier", "member_expression"):
                                ext_target = sc
                                break
                    if ext_target is not None:
                        ext_name = _node_text(ext_target, self._source)
                        modifiers.append(f"extends:{ext_name}")
                elif child.type == "implements_clause":
                    for ic in child.children:
                        if ic.type == "type_identifier":
                            impl_name = _node_text(ic, self._source)
                            modifiers.append(f"implements:{impl_name}")
        cid = self._next_id()
        sym = SemanticNode(
            id=cid,
            type=NodeType.CLASS,
            name=name,
            qualified_name=self._qname(name),
            file_path=self.file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            modifiers=tuple(modifiers),
        )
        self.symbols.append(sym)
        self._add_contains(parent_id, cid, node.start_point[0] + 1)
        body = _child_by_type(node, "class_body")
        if body is not None:
            for child in body.children:
                if child.type == "method_definition":
                    self._handle_method_definition(child, cid)
                elif child.type == "public_field_definition" or child.type == "field_definition":
                    self._handle_field_definition(child, cid)
        for mod in modifiers:
            if mod.startswith("extends:"):
                target_name = mod[len("extends:"):]
                self.relations.append(
                    SemanticRelation(
                        source=cid,
                        target=target_name,
                        type=RelationType.INHERITS,
                        evidence_file=self.file_path,
                        evidence_line=node.start_point[0] + 1,
                    )
                )
            elif mod.startswith("implements:"):
                target_name = mod[len("implements:"):]
                self.relations.append(
                    SemanticRelation(
                        source=cid,
                        target=target_name,
                        type=RelationType.IMPLEMENTS,
                        evidence_file=self.file_path,
                        evidence_line=node.start_point[0] + 1,
                    )
                )

    def _handle_method_definition(self, node, class_id: str) -> None:
        name_node = _child_by_type(node, "property_identifier")
        if name_node is None:
            return
        name = _node_text(name_node, self._source)
        params_node = _child_by_type(node, "formal_parameters")
        params = ""
        if params_node is not None:
            params = _node_text(params_node, self._source)
        method_mods: list[str] = []
        for child in node.children:
            if child.type == "accessibility_modifier":
                method_mods.append(_node_text(child, self._source))
            elif child.type == "static":
                method_mods.append("static")
            elif child.type == "async":
                method_mods.append("async")
            elif child.type == "readonly":
                method_mods.append("readonly")
        signature = f"{' '.join(method_mods + [''])}{name}{params}".strip()
        mid = self._next_id()
        sym = SemanticNode(
            id=mid,
            type=NodeType.METHOD,
            name=name,
            qualified_name=self._qname(name),
            file_path=self.file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=signature,
            modifiers=tuple(method_mods),
        )
        self.symbols.append(sym)
        self._add_contains(class_id, mid, node.start_point[0] + 1)
        if params_node is not None:
            self._extract_params(params_node, mid)

    def _handle_field_definition(self, node, class_id: str) -> None:
        name_node = None
        for child in node.children:
            if child.type in ("property_identifier", "identifier"):
                name_node = child
                break
        if name_node is None:
            return
        name = _node_text(name_node, self._source)
        fid = self._next_id()
        sym = SemanticNode(
            id=fid,
            type=NodeType.VARIABLE,
            name=name,
            qualified_name=self._qname(name),
            file_path=self.file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
        )
        self.symbols.append(sym)
        self._add_contains(class_id, fid, node.start_point[0] + 1)

    def _handle_import_statement(self, node, parent_id: str) -> None:
        source_node = _child_by_type(node, "string")
        source = ""
        if source_node is not None:
            raw = _node_text(source_node, self._source)
            source = raw.strip("'\"`")
        imported_names: list[str] = []
        import_clause = _child_by_type(node, "import_clause")
        if import_clause is not None:
            for child in import_clause.children:
                if child.type == "identifier":
                    imported_names.append(_node_text(child, self._source))
                elif child.type == "named_imports":
                    for spec in child.children:
                        if spec.type == "import_specifier":
                            spec_name = spec.child_by_field_name("name")
                            if spec_name is None:
                                for sc in spec.children:
                                    if sc.type == "identifier":
                                        spec_name = sc
                                        break
                            if spec_name is not None:
                                imported_names.append(_node_text(spec_name, self._source))
                elif child.type == "namespace_import":
                    ns_name = child.child_by_field_name("name")
                    if ns_name is not None:
                        imported_names.append(_node_text(ns_name, self._source))
        iid = self._next_id()
        sig_parts = ", ".join(imported_names) if imported_names else "*"
        signature = f"import {{ {sig_parts} }} from '{source}'"
        sym = SemanticNode(
            id=iid,
            type=NodeType.IMPORT,
            name=source,
            qualified_name=self._qname(f"import:{source}"),
            file_path=self.file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=signature,
        )
        self.symbols.append(sym)
        self._add_contains(parent_id, iid, node.start_point[0] + 1)
        if source:
            self.relations.append(
                SemanticRelation(
                    source=self.module_qualified_name,
                    target=source,
                    type=RelationType.IMPORTS,
                    evidence_file=self.file_path,
                    evidence_line=node.start_point[0] + 1,
                )
            )

    def _handle_variable_declarator(self, node, parent_id: str) -> None:
        name_node = _child_by_type(node, "identifier")
        if name_node is None:
            return
        value_node = _child_by_type(node, "=")
        if value_node is not None:
            for sibling in node.children:
                if sibling.type in ("arrow_function", "function_expression"):
                    return
        name = _node_text(name_node, self._source)
        vid = self._next_id()
        sym = SemanticNode(
            id=vid,
            type=NodeType.VARIABLE,
            name=name,
            qualified_name=self._qname(name),
            file_path=self.file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
        )
        self.symbols.append(sym)
        self._add_contains(parent_id, vid, node.start_point[0] + 1)

    def _handle_call_expression(self, node, parent_id: str) -> None:
        func_node = node.child_by_field_name("function")
        if func_node is None:
            return
        target = ""
        if func_node.type == "identifier":
            target = _node_text(func_node, self._source)
        elif func_node.type == "member_expression":
            obj_node = func_node.child_by_field_name("object")
            prop_node = func_node.child_by_field_name("property")
            if obj_node is not None and prop_node is not None:
                obj = _node_text(obj_node, self._source)
                prop = _node_text(prop_node, self._source)
                target = f"{obj}.{prop}"
            else:
                target = _node_text(func_node, self._source)
        else:
            target = _node_text(func_node, self._source)
        if target:
            self.relations.append(
                SemanticRelation(
                    source=self.module_qualified_name,
                    target=target,
                    type=RelationType.CALLS,
                    evidence_file=self.file_path,
                    evidence_line=node.start_point[0] + 1,
                )
            )

    def _handle_decorator(self, node, parent_id: str) -> None:
        name = ""
        for child in node.children:
            if child.type == "identifier":
                name = _node_text(child, self._source)
                break
            elif child.type == "call_expression":
                func_node = child.child_by_field_name("function")
                if func_node is not None:
                    name = _node_text(func_node, self._source)
                break
        if not name:
            return
        did = self._next_id()
        sym = SemanticNode(
            id=did,
            type=NodeType.DECORATOR,
            name=name,
            qualified_name=self._qname(f"@{name}"),
            file_path=self.file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
        )
        self.symbols.append(sym)
        self._add_contains(parent_id, did, node.start_point[0] + 1)
        decorated = node.parent
        if decorated is not None:
            decorated_name = None
            for child in decorated.children:
                if child.type == "identifier":
                    decorated_name = _node_text(child, self._source)
                    break
            if decorated_name is not None:
                self.relations.append(
                    SemanticRelation(
                        source=did,
                        target=decorated_name,
                        type=RelationType.DECORATES,
                        evidence_file=self.file_path,
                        evidence_line=node.start_point[0] + 1,
                    )
                )

    def _extract_params(self, params_node, parent_id: str) -> None:
        for child in params_node.children:
            if child.type in ("identifier", "required_parameter", "optional_parameter"):
                pname = ""
                for sc in child.children:
                    if sc.type == "identifier":
                        pname = _node_text(sc, self._source)
                        break
                if not pname and child.type == "identifier":
                    pname = _node_text(child, self._source)
                if pname:
                    pid = self._next_id()
                    psym = SemanticNode(
                        id=pid,
                        type=NodeType.PARAMETER,
                        name=pname,
                        qualified_name=self._qname(pname),
                        file_path=self.file_path,
                        line_start=child.start_point[0] + 1,
                        line_end=child.end_point[0] + 1,
                    )
                    self.symbols.append(psym)
                    self._add_contains(parent_id, pid, child.start_point[0] + 1)


def _parse_with_tree_sitter(content: str, language: str):
    import tree_sitter as ts

    lang_obj = _get_language(language)
    if lang_obj is None:
        return None

    try:
        lang = ts.Language(lang_obj)
        parser = ts.Parser(lang)
    except TypeError:
        parser = ts.Parser()
        parser.set_language(lang_obj)

    tree = parser.parse(content.encode("utf-8"))
    return tree


def parse_jsts_file(
    file_path: str,
    content: str,
    language: str = "javascript",
    max_symbols: int = 500,
) -> ParseResult:
    if not is_tree_sitter_available():
        return ParseResult(
            symbols=[],
            relations=[],
            status=ParseStatus.UNAVAILABLE,
            error="tree-sitter not installed",
        )

    resolved_lang = _resolve_language(file_path, language)
    qualified_name = _make_qualified_name(file_path)

    try:
        tree = _parse_with_tree_sitter(content, resolved_lang)
    except Exception as exc:
        return ParseResult(
            symbols=[],
            relations=[],
            status=ParseStatus.FAILED,
            error=str(exc),
        )

    if tree is None:
        return ParseResult(
            symbols=[],
            relations=[],
            status=ParseStatus.UNAVAILABLE,
            error=f"grammar for '{resolved_lang}' not available",
        )

    visitor = JsTsVisitor(
        file_path=file_path,
        module_qualified_name=qualified_name,
        tree=tree,
    )

    try:
        visitor.visit(content.encode("utf-8"))
    except Exception as exc:
        return ParseResult(
            symbols=visitor.symbols,
            relations=visitor.relations,
            status=ParseStatus.PARTIAL,
            error=str(exc),
        )

    truncated = False
    if len(visitor.symbols) > max_symbols:
        visitor.symbols = visitor.symbols[:max_symbols]
        valid_ids = {s.id for s in visitor.symbols}
        visitor.relations = [
            r for r in visitor.relations if r.source in valid_ids
        ]
        truncated = True

    status = ParseStatus.SUCCESS if not truncated else ParseStatus.PARTIAL
    error = ""
    if truncated:
        error = f"truncated to {max_symbols} symbols"

    if tree.root_node.has_error:
        status = ParseStatus.PARTIAL
        if not error:
            error = "parse tree contains errors"

    return ParseResult(
        symbols=visitor.symbols,
        relations=visitor.relations,
        status=status,
        error=error,
    )
