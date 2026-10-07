from __future__ import annotations

import ast

from core.intelligence.code_index.build.types import DraftRelation, ParsedFunction
from core.intelligence.code_index.enums import EntityType, RelationType
from core.intelligence.code_index.parsers.imports import ImportBinding, entity_key_for_qn


def _entity_key(entity_type: EntityType, file_path: str, qn: str) -> str:
    return entity_key_for_qn(entity_type.value, file_path, qn)


def _local_class_bindings(
    fn_node: ast.AST,
    module_name: str,
    import_bindings: dict[str, ImportBinding],
) -> dict[str, str]:
    """Map local variable names to class qualified names from `Var = ClassName(...)` assignments."""
    bindings: dict[str, str] = {}
    for node in ast.walk(fn_node):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Call):
                if isinstance(node.value.func, ast.Name):
                    name = node.value.func.id
                    imp = import_bindings.get(name)
                    if imp and imp.target_entity_qn:
                        bindings[target.id] = imp.target_entity_qn
                    else:
                        bindings[target.id] = f"{module_name}.{name}"
                elif isinstance(node.value.func, ast.Attribute):
                    bindings[target.id] = ast.unparse(node.value.func)
    return bindings


def analyze_calls(
    *,
    file_path: str,
    module_name: str,
    fn: ParsedFunction,
    bindings: dict[str, ImportBinding],
    module_index: dict[str, str],
    class_methods: dict[str, str],
    known_entities: set[str],
) -> tuple[list[DraftRelation], list[str]]:
    relations: list[DraftRelation] = []
    unresolved: list[str] = []
    node = fn.body_node
    if node is None:
        return relations, unresolved

    source_key = _entity_key(
        EntityType.METHOD if fn.is_method else EntityType.FUNCTION,
        file_path,
        fn.qualified_name,
    )

    local_classes = _local_class_bindings(node, module_name, bindings)

    class _Resolver(ast.NodeVisitor):
        def visit_Call(self, call: ast.Call) -> None:
            target_key, confidence = resolve_call(
                call.func,
                module_name=module_name,
                file_path=file_path,
                fn=fn,
                bindings=bindings,
                module_index=module_index,
                class_methods=class_methods,
                known_entities=known_entities,
                local_classes=local_classes,
            )
            if target_key:
                relations.append(
                    DraftRelation(
                        source_key=source_key,
                        target_key=target_key,
                        relation=RelationType.CALLS,
                        provenance="AST",
                        confidence=confidence,
                    )
                )
            else:
                unresolved.append(ast.unparse(call.func))
            self.generic_visit(call)

    _Resolver().visit(node)
    return relations, unresolved


def resolve_call(
    func: ast.expr,
    *,
    module_name: str,
    file_path: str,
    fn: ParsedFunction,
    bindings: dict[str, ImportBinding],
    module_index: dict[str, str],
    class_methods: dict[str, str],
    known_entities: set[str],
    local_classes: dict[str, str] | None = None,
) -> tuple[str | None, float]:
    local_classes = local_classes or {}
    if isinstance(func, ast.Name):
        local = func.id
        class_qn = local_classes.get(local) or (
            f"{module_name}.{local}" if local[0].isupper() else None
        )
        if class_qn:
            for path in {file_path, *module_index.values()}:
                key = _entity_key(EntityType.CLASS, path, class_qn)
                if key in known_entities:
                    return key, 1.0
        if local in bindings:
            binding = bindings[local]
            if binding.target_entity_qn:
                for et in (EntityType.CLASS, EntityType.FUNCTION, EntityType.METHOD):
                    for path in {file_path, *module_index.values()}:
                        key = _entity_key(et, path, binding.target_entity_qn)
                        if key in known_entities:
                            return key, 1.0
        key = _entity_key(
            EntityType.FUNCTION if not fn.is_method else EntityType.METHOD,
            file_path,
            f"{module_name}.{local}",
        )
        if key in known_entities:
            return key, 1.0
        return None, 0.0

    if isinstance(func, ast.Attribute):
        if isinstance(func.value, ast.Name):
            var = func.value.id
            class_qn = local_classes.get(var)
            if class_qn:
                method_qn = f"{class_qn}.{func.attr}"
                for path in {file_path, *module_index.values()}:
                    key = _entity_key(EntityType.METHOD, path, method_qn)
                    if key in known_entities:
                        return key, 1.0
        if (
            isinstance(func.value, ast.Attribute)
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "self"
            and fn.class_name
        ):
            for key in known_entities:
                if (
                    EntityType.METHOD.value in key
                    and key.endswith(f".{func.attr}")
                    and "METHOD:" in key
                ):
                    qn = key.split(":", 2)[-1]
                    if qn.count(".") >= 2:
                        return key, 0.8
        if isinstance(func.value, ast.Name) and func.value.id == "self" and fn.class_name:
            method_qn = f"{module_name}.{fn.class_name}.{func.attr}"
            key = _entity_key(EntityType.METHOD, file_path, method_qn)
            if key in known_entities:
                return key, 0.8
        if isinstance(func.value, ast.Name):
            import_binding = bindings.get(func.value.id)
            if import_binding and import_binding.target_entity_qn:
                class_qn = import_binding.target_entity_qn
                method_qn = f"{class_qn}.{func.attr}"
                for path in module_index.values():
                    key = _entity_key(EntityType.METHOD, path, method_qn)
                    if key in known_entities:
                        return key, 1.0
                inst_key = _entity_key(EntityType.CLASS, file_path, class_qn)
                if inst_key in known_entities:
                    ctor = _entity_key(EntityType.METHOD, file_path, f"{class_qn}.__init__")
                    if ctor in known_entities:
                        return ctor, 1.0
        return None, 0.0

    return None, 0.0
