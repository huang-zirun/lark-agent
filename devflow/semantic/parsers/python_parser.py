from __future__ import annotations

import ast
from dataclasses import dataclass, field

from devflow.semantic.models import (
    NodeType,
    ParseStatus,
    RelationType,
    SemanticNode,
    SemanticRelation,
)


@dataclass(slots=True)
class ParseResult:
    symbols: list[SemanticNode] = field(default_factory=list)
    relations: list[SemanticRelation] = field(default_factory=list)
    status: ParseStatus = ParseStatus.SUCCESS
    error: str = ""
    truncated: bool = False


def _file_path_to_module(file_path: str) -> str:
    parts = file_path.replace("\\", "/")
    if parts.endswith(".py"):
        parts = parts[:-3]
    return parts.replace("/", ".")


class PythonSemanticVisitor(ast.NodeVisitor):

    def __init__(self, file_path: str, module_qualified_name: str) -> None:
        self.file_path = file_path
        self.module_qualified_name = module_qualified_name
        self.symbols: list[SemanticNode] = []
        self.relations: list[SemanticRelation] = []
        self._class_stack: list[str] = []
        self._current_class_id: str | None = None
        self._parent_id: str | None = None

    def _make_qualified_name(self, name: str) -> str:
        if self._class_stack:
            return f"{self.module_qualified_name}.{'.'.join(self._class_stack)}.{name}"
        return f"{self.module_qualified_name}.{name}"

    def _get_decorator_names(self, decorator_list: list[ast.expr]) -> tuple[str, ...]:
        names: list[str] = []
        for dec in decorator_list:
            if isinstance(dec, ast.Name):
                names.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                names.append(self._resolve_attr_name(dec))
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    names.append(dec.func.id)
                elif isinstance(dec.func, ast.Attribute):
                    names.append(self._resolve_attr_name(dec.func))
        return tuple(names)

    def _resolve_attr_name(self, node: ast.Attribute) -> str:
        parts: list[str] = []
        current: ast.expr = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        parts.reverse()
        return ".".join(parts)

    def _build_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        args = node.args
        parts: list[str] = []

        for arg in args.posonlyargs:
            parts.append(self._format_arg(arg))
        if args.posonlyargs:
            parts.append("/")

        for arg in args.args:
            parts.append(self._format_arg(arg))

        if args.vararg:
            parts.append(f"*{args.vararg.arg}")
            if args.vararg.annotation:
                parts[-1] = f"*{args.vararg.arg}: {self._annotation_str(args.vararg.annotation)}"

        if not args.vararg and args.kwonlyargs:
            parts.append("*")

        for i, arg in enumerate(args.kwonlyargs):
            default_idx = i - (len(args.kwonlyargs) - len(args.kw_defaults))
            default = args.kw_defaults[i] if i < len(args.kw_defaults) else None
            s = self._format_arg(arg)
            if default is not None:
                s += f" = {self._default_str(default)}"
            parts.append(s)

        if args.kwarg:
            parts.append(f"**{args.kwarg.arg}")
            if args.kwarg.annotation:
                parts[-1] = f"**{args.kwarg.arg}: {self._annotation_str(args.kwarg.annotation)}"

        sig = f"({', '.join(parts)})"
        if node.returns:
            sig += f" -> {self._annotation_str(node.returns)}"
        return sig

    def _format_arg(self, arg: ast.arg) -> str:
        if arg.annotation:
            return f"{arg.arg}: {self._annotation_str(arg.annotation)}"
        return arg.arg

    def _annotation_str(self, node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return self._resolve_attr_name(node)
        if isinstance(node, ast.Subscript):
            return f"{self._annotation_str(node.value)}[{self._annotation_str(node.slice)}]"
        if isinstance(node, ast.Constant):
            return repr(node.value)
        if isinstance(node, ast.Tuple):
            return ", ".join(self._annotation_str(elt) for elt in node.elts)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return f"{self._annotation_str(node.left)} | {self._annotation_str(node.right)}"
        if isinstance(node, ast.Index):
            return self._annotation_str(node.value)
        return "..."

    def _default_str(self, node: ast.expr) -> str:
        if isinstance(node, ast.Constant):
            return repr(node.value)
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return self._resolve_attr_name(node)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return f"-{self._default_str(node.operand)}"
        if isinstance(node, ast.List):
            return "[" + ", ".join(self._default_str(e) for e in node.elts) + "]"
        if isinstance(node, ast.Tuple):
            return "(" + ", ".join(self._default_str(e) for e in node.elts) + ")"
        if isinstance(node, ast.Dict):
            items = ", ".join(
                f"{self._default_str(k)}: {self._default_str(v)}"
                for k, v in zip(node.keys, node.values)
                if k is not None
            )
            return "{" + items + "}"
        if isinstance(node, ast.Call):
            return "..."
        return "..."

    def _resolve_call_target(self, func_node: ast.expr) -> str:
        if isinstance(func_node, ast.Name):
            return func_node.id
        if isinstance(func_node, ast.Attribute):
            if isinstance(func_node.value, ast.Name) and func_node.value.id == "self":
                if self._class_stack:
                    return f"{self._class_stack[-1]}.{func_node.attr}"
            return self._resolve_attr_name(func_node)
        return ""

    def _extract_call_relations(self, node: ast.Call, parent_id: str) -> None:
        target = self._resolve_call_target(node.func)
        if not target:
            return
        self.relations.append(
            SemanticRelation(
                source=parent_id,
                target=target,
                type=RelationType.CALLS,
                evidence_file=self.file_path,
                evidence_line=node.lineno,
            )
        )

    def _visit_function_body_for_calls(self, node: ast.FunctionDef | ast.AsyncFunctionDef, parent_id: str) -> None:
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and child is not node:
                self._extract_call_relations(child, parent_id)

    def _add_contains_relation(self, parent_id: str, child_id: str) -> None:
        self.relations.append(
            SemanticRelation(
                source=parent_id,
                target=child_id,
                type=RelationType.CONTAINS,
                evidence_file=self.file_path,
                evidence_line=0,
            )
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        node_id = f"{self.file_path}:class:{node.name}:{node.lineno}"
        qualified_name = self._make_qualified_name(node.name)

        bases: list[str] = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(self._resolve_attr_name(base))

        decorator_names = self._get_decorator_names(node.decorator_list)
        docstring = ast.get_docstring(node) or ""

        sig = f"({', '.join(bases)})" if bases else ""

        class_node = SemanticNode(
            id=node_id,
            type=NodeType.CLASS,
            name=node.name,
            qualified_name=qualified_name,
            file_path=self.file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            signature=sig,
            docstring=docstring,
            modifiers=decorator_names,
        )
        self.symbols.append(class_node)

        if self._parent_id:
            self._add_contains_relation(self._parent_id, node_id)

        for base_name in bases:
            self.relations.append(
                SemanticRelation(
                    source=node_id,
                    target=base_name,
                    type=RelationType.INHERITS,
                    evidence_file=self.file_path,
                    evidence_line=node.lineno,
                )
            )

        prev_parent = self._parent_id
        prev_class_id = self._current_class_id
        self._parent_id = node_id
        self._current_class_id = node_id
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()
        self._parent_id = prev_parent
        self._current_class_id = prev_class_id

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        is_method = len(self._class_stack) > 0
        node_type = NodeType.METHOD if is_method else NodeType.FUNCTION
        type_str = "method" if is_method else "function"

        node_id = f"{self.file_path}:{type_str}:{node.name}:{node.lineno}"
        qualified_name = self._make_qualified_name(node.name)

        signature = self._build_signature(node)
        decorator_names = self._get_decorator_names(node.decorator_list)
        docstring = ast.get_docstring(node) or ""

        modifiers: list[str] = []
        if isinstance(node, ast.AsyncFunctionDef):
            modifiers.append("async")
        modifiers.extend(decorator_names)

        func_node = SemanticNode(
            id=node_id,
            type=node_type,
            name=node.name,
            qualified_name=qualified_name,
            file_path=self.file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            signature=signature,
            docstring=docstring,
            modifiers=tuple(modifiers),
        )
        self.symbols.append(func_node)

        if self._parent_id:
            self._add_contains_relation(self._parent_id, node_id)

        self._visit_function_body_for_calls(node, node_id)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name = alias.name
            asname = alias.asname or ""
            sig = f"as {asname}" if asname else ""
            node_id = f"{self.file_path}:import:{name}:{node.lineno}"

            import_node = SemanticNode(
                id=node_id,
                type=NodeType.IMPORT,
                name=name,
                qualified_name=f"{self.module_qualified_name}.{asname}" if asname else f"{self.module_qualified_name}.{name}",
                file_path=self.file_path,
                line_start=node.lineno,
                line_end=node.end_lineno or node.lineno,
                signature=sig,
            )
            self.symbols.append(import_node)

            self.relations.append(
                SemanticRelation(
                    source=self._parent_id or f"{self.file_path}:module",
                    target=name,
                    type=RelationType.IMPORTS,
                    evidence_file=self.file_path,
                    evidence_line=node.lineno,
                )
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        imported_names = [alias.name for alias in node.names]
        sig = f"from {module} import {', '.join(imported_names)}"

        node_id = f"{self.file_path}:import:{module}:{node.lineno}"

        import_node = SemanticNode(
            id=node_id,
            type=NodeType.IMPORT,
            name=module,
            qualified_name=f"{self.module_qualified_name}.{module}" if module else self.module_qualified_name,
            file_path=self.file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            signature=sig,
        )
        self.symbols.append(import_node)

        for alias in node.names:
            target = f"{module}.{alias.name}" if module else alias.name
            self.relations.append(
                SemanticRelation(
                    source=self._parent_id or f"{self.file_path}:module",
                    target=target,
                    type=RelationType.IMPORTS,
                    evidence_file=self.file_path,
                    evidence_line=node.lineno,
                )
            )

    def _extract_target_names(self, target: ast.expr) -> list[str]:
        if isinstance(target, ast.Name):
            return [target.id]
        if isinstance(target, (ast.Tuple, ast.List)):
            names: list[str] = []
            for elt in target.elts:
                names.extend(self._extract_target_names(elt))
            return names
        if isinstance(target, ast.Starred):
            return self._extract_target_names(target.value)
        return []

    def visit_Assign(self, node: ast.Assign) -> None:
        if not self._class_stack and self._parent_id is not None:
            if self._parent_id and not self._parent_id.endswith(":module"):
                return

        for target in node.targets:
            names = self._extract_target_names(target)
            for name in names:
                var_id = f"{self.file_path}:variable:{name}:{node.lineno}"
                qualified_name = self._make_qualified_name(name)

                var_node = SemanticNode(
                    id=var_id,
                    type=NodeType.VARIABLE,
                    name=name,
                    qualified_name=qualified_name,
                    file_path=self.file_path,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                )
                self.symbols.append(var_node)

                if self._parent_id:
                    self._add_contains_relation(self._parent_id, var_id)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if not self._class_stack and self._parent_id is not None:
            if self._parent_id and not self._parent_id.endswith(":module"):
                return

        if not isinstance(node.target, ast.Name):
            return

        name = node.target.id
        annotation_str = self._annotation_str(node.annotation)
        default_str = ""
        if node.value is not None:
            default_str = f" = {self._default_str(node.value)}"
        sig = f"{annotation_str}{default_str}"

        var_id = f"{self.file_path}:variable:{name}:{node.lineno}"
        qualified_name = self._make_qualified_name(name)

        var_node = SemanticNode(
            id=var_id,
            type=NodeType.VARIABLE,
            name=name,
            qualified_name=qualified_name,
            file_path=self.file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            signature=sig,
        )
        self.symbols.append(var_node)

        if self._parent_id:
            self._add_contains_relation(self._parent_id, var_id)


def parse_python_file(file_path: str, content: str, max_symbols: int = 500) -> ParseResult:
    result = ParseResult(status=ParseStatus.SUCCESS)

    try:
        tree = ast.parse(content, filename=file_path)
    except SyntaxError as e:
        result.status = ParseStatus.FAILED
        result.error = f"SyntaxError: {e.msg} at line {e.lineno}"
        return result

    module_name = _file_path_to_module(file_path)
    visitor = PythonSemanticVisitor(file_path, module_name)
    visitor.visit(tree)

    result.symbols = visitor.symbols
    result.relations = visitor.relations

    if len(result.symbols) > max_symbols:
        top_level_ids: set[str] = set()
        for sym in result.symbols:
            if sym.type in (NodeType.CLASS, NodeType.FUNCTION, NodeType.IMPORT):
                if ":" in sym.id:
                    parts = sym.id.split(":")
                    if len(parts) >= 2 and parts[1] in ("class", "function", "import"):
                        top_level_ids.add(sym.id)

        result.symbols = [s for s in result.symbols if s.id in top_level_ids]
        result.relations = [
            r for r in result.relations
            if r.source in top_level_ids or r.source.endswith(":module")
        ]
        result.status = ParseStatus.PARTIAL
        result.truncated = True

    return result
