from __future__ import annotations

import ast
import hashlib

from core.intelligence.code_index.build.types import ParsedClass, ParsedFunction, ParsedModule
from core.intelligence.code_index.parsers.module_map import path_to_module


def _decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_decorator_name(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return "unknown"


def _signature_simple(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = ast.unparse(node.args)
    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"({args}){returns}"


_DocstringNode = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Module


def _doc_first_line(node: _DocstringNode) -> str | None:
    doc = ast.get_docstring(node)
    if not doc:
        return None
    line = doc.strip().splitlines()[0].strip()
    return line or None


def entity_body_hash(*parts: str) -> str:
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_module(file_path: str, source: str) -> ParsedModule:
    module_name = path_to_module(file_path)
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError as exc:
        return ParsedModule(
            file_path=file_path,
            module_name=module_name,
            source=source,
            tree=None,
            functions=[],
            classes=[],
            parse_error=str(exc),
        )

    functions: list[ParsedFunction] = []
    classes: list[ParsedClass] = []

    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name.startswith("_") and node.name != "__init__":
                is_public = False
            else:
                is_public = not node.name.startswith("_")
            functions.append(
                ParsedFunction(
                    name=node.name,
                    qualified_name=f"{module_name}.{node.name}",
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    is_method=False,
                    class_name=None,
                    decorators=[_decorator_name(d) for d in node.decorator_list],
                    signature=_signature_simple(node),
                    doc_first_line=_doc_first_line(node),
                    is_public=is_public,
                    body_node=node,
                )
            )
        elif isinstance(node, ast.ClassDef):
            methods: list[ParsedFunction] = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    is_public = item.name == "__init__" or not item.name.startswith("_")
                    methods.append(
                        ParsedFunction(
                            name=item.name,
                            qualified_name=f"{module_name}.{node.name}.{item.name}",
                            start_line=item.lineno,
                            end_line=item.end_lineno or item.lineno,
                            is_method=True,
                            class_name=node.name,
                            decorators=[_decorator_name(d) for d in item.decorator_list],
                            signature=_signature_simple(item),
                            doc_first_line=_doc_first_line(item),
                            is_public=is_public,
                            body_node=item,
                        )
                    )
            bases = [ast.unparse(b) for b in node.bases]
            classes.append(
                ParsedClass(
                    name=node.name,
                    qualified_name=f"{module_name}.{node.name}",
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    bases=bases,
                    decorators=[_decorator_name(d) for d in node.decorator_list],
                    doc_first_line=_doc_first_line(node),
                    is_public=not node.name.startswith("_"),
                    methods=methods,
                    node=node,
                )
            )

    return ParsedModule(
        file_path=file_path,
        module_name=module_name,
        source=source,
        tree=tree,
        functions=functions,
        classes=classes,
    )


def walk_nested_classes(module: ParsedModule) -> list[ParsedClass]:
    """Include nested classes from AST (not flattened in initial parse)."""
    if module.tree is None:
        return module.classes

    found: list[ParsedClass] = list(module.classes)

    def visit_class(class_node: ast.ClassDef, prefix: str) -> None:
        for item in class_node.body:
            if isinstance(item, ast.ClassDef):
                qn = f"{prefix}.{item.name}"
                nested_methods: list[ParsedFunction] = []
                for m in item.body:
                    if isinstance(m, ast.FunctionDef | ast.AsyncFunctionDef):
                        nested_methods.append(
                            ParsedFunction(
                                name=m.name,
                                qualified_name=f"{qn}.{m.name}",
                                start_line=m.lineno,
                                end_line=m.end_lineno or m.lineno,
                                is_method=True,
                                class_name=item.name,
                                decorators=[_decorator_name(d) for d in m.decorator_list],
                                signature=_signature_simple(m),
                                doc_first_line=_doc_first_line(m),
                                is_public=not m.name.startswith("_"),
                                body_node=m,
                            )
                        )
                found.append(
                    ParsedClass(
                        name=item.name,
                        qualified_name=qn,
                        start_line=item.lineno,
                        end_line=item.end_lineno or item.lineno,
                        bases=[ast.unparse(b) for b in item.bases],
                        decorators=[_decorator_name(d) for d in item.decorator_list],
                        doc_first_line=_doc_first_line(item),
                        is_public=not item.name.startswith("_"),
                        methods=nested_methods,
                        node=item,
                    )
                )
                visit_class(item, qn)

    for node in module.tree.body:
        if isinstance(node, ast.ClassDef):
            visit_class(node, f"{module.module_name}.{node.name}")

    return found
