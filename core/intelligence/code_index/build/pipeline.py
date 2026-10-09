from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.domain.canonical_json import sha256_hex
from core.intelligence.code_index.build.types import DraftEntity, DraftRelation
from core.intelligence.code_index.enums import EntityType, RelationType
from core.intelligence.code_index.parsers.calls import analyze_calls
from core.intelligence.code_index.parsers.frameworks import (
    fastapi_routes,
    pydantic_schemas,
    pytest_tests,
    sqlalchemy_models,
)
from core.intelligence.code_index.parsers.imports import (
    analyze_imports,
    module_entity_key,
    parse_declared_dependencies,
)
from core.intelligence.code_index.parsers.inheritance import analyze_inheritance
from core.intelligence.code_index.parsers.module_map import (
    build_module_index,
    package_paths,
)
from core.intelligence.code_index.parsers.python_ast import (
    entity_body_hash,
    parse_module,
    walk_nested_classes,
)
from core.intelligence.code_index.stable_keys import entity_stable_key
from core.intelligence.repository.git_source import GitSourceReader


@dataclass
class BuildResult:
    entities: list[DraftEntity] = field(default_factory=list)
    relations: list[DraftRelation] = field(default_factory=list)
    parse_errors: dict[str, str] = field(default_factory=dict)
    stats: dict[str, Any] = field(default_factory=dict)


def _finalize_entity(entity: DraftEntity) -> DraftEntity:
    if not entity.content_hash:
        entity.content_hash = entity_body_hash(
            entity.qualified_name,
            entity.metadata.get("signature", ""),
            str(entity.start_line),
            str(entity.end_line),
        )
    return entity


def build_index_from_sources(
    *,
    repository_name: str,
    commit_sha: str,
    py_sources: dict[str, str],
    manifests: dict[str, str],
    git_reader: GitSourceReader | None = None,
) -> BuildResult:
    result = BuildResult()
    module_index = build_module_index(py_sources)
    declared = parse_declared_dependencies(manifests)

    repo_key = entity_stable_key(
        EntityType.REPOSITORY, file_path=None, qualified_name=repository_name
    )
    result.entities.append(
        _finalize_entity(
            DraftEntity(
                stable_key=repo_key,
                type=EntityType.REPOSITORY,
                qualified_name=repository_name,
                metadata={"commit_sha": commit_sha},
            )
        )
    )

    for pkg in package_paths(py_sources):
        pkg_key = entity_stable_key(EntityType.PACKAGE, file_path=pkg, qualified_name=pkg)
        ent = DraftEntity(
            stable_key=pkg_key,
            type=EntityType.PACKAGE,
            qualified_name=pkg,
            file_path=pkg,
        )
        result.entities.append(_finalize_entity(ent))
        result.relations.append(DraftRelation(repo_key, pkg_key, RelationType.CONTAINS, "AST"))

    parsed_modules = []
    for path, source in sorted(py_sources.items()):
        mod = parse_module(path, source)
        parsed_modules.append(mod)
        if mod.parse_error:
            result.parse_errors[path] = mod.parse_error
            continue

        mod_key = module_entity_key(path)
        file_key = entity_stable_key(EntityType.FILE, file_path=path, qualified_name=path)
        mod_ent = DraftEntity(
            stable_key=mod_key,
            type=EntityType.MODULE,
            qualified_name=mod.module_name,
            file_path=path,
        )
        file_ent = DraftEntity(
            stable_key=file_key,
            type=EntityType.FILE,
            qualified_name=path,
            file_path=path,
        )
        if git_reader is not None:
            meta = git_reader.file_metadata_at_commit(commit_sha, path)
            if meta:
                file_ent.metadata["git"] = {
                    "last_commit_sha": meta.last_commit_sha,
                    "author_date": meta.author_date,
                    "commit_count": meta.commit_count,
                }
        result.entities.extend([_finalize_entity(mod_ent), _finalize_entity(file_ent)])
        pkg = "/".join(path.split("/")[:-1]) if "/" in path else ""
        if pkg:
            pkg_key = entity_stable_key(EntityType.PACKAGE, file_path=pkg, qualified_name=pkg)
            result.relations.append(DraftRelation(pkg_key, mod_key, RelationType.CONTAINS, "AST"))
        result.relations.append(DraftRelation(mod_key, file_key, RelationType.CONTAINS, "AST"))

        for cls in walk_nested_classes(mod):
            cls_key = entity_stable_key(
                EntityType.CLASS, file_path=path, qualified_name=cls.qualified_name
            )
            result.entities.append(
                _finalize_entity(
                    DraftEntity(
                        stable_key=cls_key,
                        type=EntityType.CLASS,
                        qualified_name=cls.qualified_name,
                        file_path=path,
                        start_line=cls.start_line,
                        end_line=cls.end_line,
                        is_public=cls.is_public,
                        metadata={
                            "decorators": cls.decorators,
                            "doc": cls.doc_first_line,
                            "bases": cls.bases,
                        },
                    )
                )
            )
            result.relations.append(DraftRelation(file_key, cls_key, RelationType.CONTAINS, "AST"))
            for method in cls.methods:
                m_key = entity_stable_key(
                    EntityType.METHOD, file_path=path, qualified_name=method.qualified_name
                )
                result.entities.append(
                    _finalize_entity(
                        DraftEntity(
                            stable_key=m_key,
                            type=EntityType.METHOD,
                            qualified_name=method.qualified_name,
                            file_path=path,
                            start_line=method.start_line,
                            end_line=method.end_line,
                            is_public=method.is_public,
                            metadata={
                                "decorators": method.decorators,
                                "signature": method.signature,
                                "doc": method.doc_first_line,
                            },
                        )
                    )
                )
                result.relations.append(DraftRelation(cls_key, m_key, RelationType.CONTAINS, "AST"))

        for fn in mod.functions:
            fn_key = entity_stable_key(
                EntityType.FUNCTION, file_path=path, qualified_name=fn.qualified_name
            )
            result.entities.append(
                _finalize_entity(
                    DraftEntity(
                        stable_key=fn_key,
                        type=EntityType.FUNCTION,
                        qualified_name=fn.qualified_name,
                        file_path=path,
                        start_line=fn.start_line,
                        end_line=fn.end_line,
                        is_public=fn.is_public,
                        metadata={
                            "decorators": fn.decorators,
                            "signature": fn.signature,
                            "doc": fn.doc_first_line,
                        },
                    )
                )
            )
            result.relations.append(DraftRelation(file_key, fn_key, RelationType.CONTAINS, "AST"))

    known = {e.stable_key for e in result.entities}

    for mod in parsed_modules:
        if mod.parse_error or mod.tree is None:
            continue
        mod_key = module_entity_key(mod.file_path)
        imp = analyze_imports(
            file_path=mod.file_path,
            module_name=mod.module_name,
            tree=mod.tree,
            module_index=module_index,
            declared_deps=declared,
            source_module_key=mod_key,
        )
        file_key = entity_stable_key(
            EntityType.FILE, file_path=mod.file_path, qualified_name=mod.file_path
        )
        file_ent_opt = next((e for e in result.entities if e.stable_key == file_key), None)
        if file_ent_opt is not None and imp.external_imports:
            file_ent_opt.metadata["external_imports"] = imp.external_imports
        result.relations.extend(imp.relations)

        for cls in walk_nested_classes(mod):
            cls_key = entity_stable_key(
                EntityType.CLASS, file_path=mod.file_path, qualified_name=cls.qualified_name
            )
            result.relations.extend(
                analyze_inheritance(
                    file_path=mod.file_path,
                    cls=cls,
                    module_index=module_index,
                    known_entities=known,
                )
            )

        bindings = imp.bindings
        class_methods = {}
        for cls in walk_nested_classes(mod):
            for method in cls.methods:
                class_methods[method.name] = method.qualified_name

        unresolved_all: list[str] = []
        for fn in mod.functions:
            rels, unresolved = analyze_calls(
                file_path=mod.file_path,
                module_name=mod.module_name,
                fn=fn,
                bindings=bindings,
                module_index=module_index,
                class_methods=class_methods,
                known_entities=known,
            )
            result.relations.extend(rels)
            unresolved_all.extend(unresolved)
        for cls in walk_nested_classes(mod):
            for method in cls.methods:
                rels, unresolved = analyze_calls(
                    file_path=mod.file_path,
                    module_name=mod.module_name,
                    fn=method,
                    bindings=bindings,
                    module_index=module_index,
                    class_methods=class_methods,
                    known_entities=known,
                )
                result.relations.extend(rels)
                unresolved_all.extend(unresolved)
        if unresolved_all and file_ent_opt is not None:
            file_ent_opt.metadata["unresolved_calls"] = sorted(set(unresolved_all))

        schema_ents, schema_rels = pydantic_schemas.extract_schemas(mod, known_entities=known)
        for ent in schema_ents:
            result.entities.append(_finalize_entity(ent))
            known.add(ent.stable_key)
            result.relations.append(
                DraftRelation(file_key, ent.stable_key, RelationType.CONTAINS, "FRAMEWORK:pydantic")
            )
        result.relations.extend(schema_rels)

        model_ents, model_rels = sqlalchemy_models.extract_models(mod)
        for ent in model_ents:
            if ent.stable_key not in known:
                result.entities.append(_finalize_entity(ent))
                known.add(ent.stable_key)
                if ent.type == EntityType.ORM_MODEL:
                    result.relations.append(
                        DraftRelation(
                            file_key, ent.stable_key, RelationType.CONTAINS, "FRAMEWORK:sqlalchemy"
                        )
                    )
        result.relations.extend(model_rels)
        result.relations.extend(sqlalchemy_models.extract_accesses(mod, known_entities=known))

        route_ents, route_rels, _ = fastapi_routes.extract_routes(mod, known_entities=known)
        for ent in route_ents:
            result.entities.append(_finalize_entity(ent))
            known.add(ent.stable_key)
        result.relations.extend(route_rels)

    route_index = {
        e.stable_key: e.metadata.get("path", "")
        for e in result.entities
        if e.type == EntityType.ROUTE
    }
    for mod in parsed_modules:
        if mod.parse_error:
            continue
        if not mod.file_path.startswith("tests/"):
            continue
        test_ents, test_rels = pytest_tests.extract_tests(
            mod, known_entities=known, route_paths=route_index
        )
        for ent in test_ents:
            result.entities.append(_finalize_entity(ent))
            known.add(ent.stable_key)
            file_key = entity_stable_key(
                EntityType.FILE, file_path=mod.file_path, qualified_name=mod.file_path
            )
            result.relations.append(
                DraftRelation(file_key, ent.stable_key, RelationType.CONTAINS, "FRAMEWORK:pytest")
            )
        result.relations.extend(test_rels)

    deduped_relations: dict[tuple[str, str, str], DraftRelation] = {}
    for rel in result.relations:
        deduped_relations[(rel.source_key, rel.relation.value, rel.target_key)] = rel
    result.relations = sorted(
        deduped_relations.values(),
        key=lambda r: (r.source_key, r.relation.value, r.target_key, r.provenance),
    )
    result.entities.sort(key=lambda e: e.stable_key)
    type_counts: dict[str, int] = {}
    rel_counts: dict[str, int] = {}
    for e in result.entities:
        type_counts[e.type.value] = type_counts.get(e.type.value, 0) + 1
    for r in result.relations:
        rel_counts[r.relation.value] = rel_counts.get(r.relation.value, 0) + 1
    result.stats = {
        "entity_counts": type_counts,
        "relation_counts": rel_counts,
        "parse_errors": len(result.parse_errors),
        "files": len(py_sources),
    }
    return result


def version_content_hash(entities: list[DraftEntity], relations: list[DraftRelation]) -> str:
    entity_part = [(e.stable_key, e.content_hash or "") for e in entities]
    entity_part.sort()
    rel_part = [
        (r.source_key, r.relation.value, r.target_key, r.provenance, r.confidence)
        for r in relations
    ]
    rel_part.sort()
    return sha256_hex({"entities": entity_part, "relations": rel_part})
