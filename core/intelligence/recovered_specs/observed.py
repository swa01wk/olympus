from __future__ import annotations

import ast
import re
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.enums import KnowledgeClass, KnowledgeItemStatus
from core.domain.events.append import append_domain_event
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.intelligence.brownfield.enums import ObservedBehaviorKind
from core.intelligence.brownfield.models import ObservedBehavior
from core.intelligence.code_index.enums import EntityType, RelationType
from core.intelligence.code_index.models import CodeEntity, CodeIndexVersion, CodeRelation
from core.intelligence.repository.git_source import GitSourceReader
from core.product_model.models import KnowledgeItem
from core.repositories.workspace_locator import WorkspaceLocator


class ObservedBehaviorService:
    async def derive(
        self,
        session: AsyncSession,
        *,
        delivery_cycle_id: uuid.UUID,
        project_id: uuid.UUID,
        index_version_id: uuid.UUID,
        commit_sha: str,
        test_results: dict[str, Any] | None,
        ctx: CommandContext,
    ) -> list[ObservedBehavior]:
        version = await session.get(CodeIndexVersion, index_version_id)
        if version is None:
            raise ValueError("index version missing")
        entities = (
            (
                await session.execute(
                    select(CodeEntity).where(CodeEntity.index_version_id == index_version_id)
                )
            )
            .scalars()
            .all()
        )
        relations = (
            (
                await session.execute(
                    select(CodeRelation).where(CodeRelation.index_version_id == index_version_id)
                )
            )
            .scalars()
            .all()
        )
        by_id = {e.id: e for e in entities}
        out: list[ObservedBehavior] = []
        seq = 0

        async def add_behavior(
            kind: ObservedBehaviorKind,
            description: str,
            subject_keys: list[str],
            evidence: list[dict[str, Any]],
            provenance: str,
            confidence: float,
            passed: bool | None = None,
        ) -> ObservedBehavior:
            nonlocal seq
            seq += 1
            fact = KnowledgeItem(
                project_id=project_id,
                delivery_cycle_id=delivery_cycle_id,
                knowledge_class=KnowledgeClass.FACT,
                statement=description,
                subject_refs=[{"stable_key": k} for k in subject_keys],
                provenance={"origin": "DETERMINISTIC", "source": kind.value},
                evidence_refs=evidence,
                status=KnowledgeItemStatus.ACTIVE,
            )
            session.add(fact)
            await session.flush()
            row = ObservedBehavior(
                key=f"OB-{seq:04d}",
                project_id=project_id,
                delivery_cycle_id=delivery_cycle_id,
                index_version_id=index_version_id,
                commit_sha=commit_sha,
                kind=kind,
                description=description,
                subject_stable_keys=subject_keys,
                evidence_refs=evidence,
                provenance=provenance,
                confidence=confidence,
                passed=passed,
                fact_item_id=fact.id,
            )
            session.add(row)
            await session.flush()
            out.append(row)
            return row

        for ent in entities:
            if ent.type != EntityType.ROUTE:
                continue
            meta = ent.entity_metadata or {}
            path = meta.get("path") or ent.qualified_name
            method = (meta.get("method") or "GET").upper()
            desc = f"Route {method} {path} handled by {ent.qualified_name}"
            subjects = [ent.stable_key]
            for rel in relations:
                if rel.source_entity_id == ent.id and rel.relation in (
                    RelationType.EXPOSES,
                    RelationType.CALLS,
                ):
                    tgt = by_id.get(rel.target_entity_id)
                    if tgt:
                        subjects.append(tgt.stable_key)
            await add_behavior(
                ObservedBehaviorKind.ROUTE_BEHAVIOR,
                desc,
                subjects,
                [{"type": "CODE_ENTITY", "ref": ent.stable_key}],
                "FRAMEWORK:fastapi",
                0.85,
            )

        for ent in entities:
            if ent.type != EntityType.ORM_MODEL:
                continue
            meta = ent.entity_metadata or {}
            for col in meta.get("columns") or []:
                name = col.get("name")
                if not name:
                    continue
                if name == "status":
                    await add_behavior(
                        ObservedBehaviorKind.DATA_INVARIANT,
                        f"ORM model {ent.qualified_name} column status present",
                        [ent.stable_key],
                        [{"type": "CODE_ENTITY", "ref": ent.stable_key, "field": name}],
                        "AST",
                        0.9,
                    )

        for ent in entities:
            if ent.type != EntityType.SCHEMA:
                continue
            meta = ent.entity_metadata or {}
            for field in meta.get("fields") or []:
                if field.get("required"):
                    fname = field.get("name", "field")
                    await add_behavior(
                        ObservedBehaviorKind.VALIDATION_RULE,
                        f"Schema {ent.qualified_name} requires field {fname}",
                        [ent.stable_key],
                        [{"type": "CODE_ENTITY", "ref": ent.stable_key}],
                        "FRAMEWORK:pydantic",
                        0.85,
                    )

        repo = await session.get(Repository, version.repository_id)
        if repo and repo.workspace_id:
            ws = await session.get(RepositoryWorkspace, repo.workspace_id)
            if ws:
                git_dir = str(WorkspaceLocator().resolve(ws.storage_backend, ws.logical_location))
                reader = GitSourceReader(git_dir)
                tests = reader.read_text_files_at_commit(commit_sha, suffixes=(".py",))
                for path, source in tests.items():
                    if "/tests/" not in path and not path.startswith("tests/"):
                        continue
                    out.extend(
                        await self._extract_test_assertions(
                            session,
                            add_behavior,
                            path,
                            source,
                            test_results,
                        )
                    )

        if test_results:
            for node in test_results.get("cases") or []:
                node_id = str(node.get("nodeid", ""))
                passed = bool(node.get("passed"))
                await add_behavior(
                    ObservedBehaviorKind.TEST_EXECUTION,
                    f"Test {node_id} {'passed' if passed else 'failed'}",
                    [node_id],
                    [{"type": "TEST_RESULT", "ref": node_id}],
                    "TEST_EXECUTION",
                    1.0 if passed else 0.5,
                    passed=passed,
                )

        await append_domain_event(
            session,
            aggregate_type="delivery_cycle",
            aggregate_id=delivery_cycle_id,
            event_type="observed_behavior.derived",
            payload={"count": len(out), "commit_sha": commit_sha},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
        )
        return out

    async def _extract_test_assertions(
        self,
        session: AsyncSession,
        add_behavior: Callable[..., Awaitable[ObservedBehavior]],
        path: str,
        source: str,
        test_results: dict[str, Any] | None,
    ) -> list[ObservedBehavior]:
        del session
        rows: list[ObservedBehavior] = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return rows
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assert):
                continue
            text = ast.get_source_segment(source, node) or ""
            if "status_code" in text:
                m = re.search(r"status_code\s*==\s*(\d+)", text)
                code = m.group(1) if m else "?"
                desc = f"Test asserts status_code == {code} in {path}"
                passed = None
                if test_results:
                    passed = test_results.get("passed")
                rows.append(
                    await add_behavior(
                        ObservedBehaviorKind.TEST_ASSERTED,
                        desc,
                        [path],
                        [{"type": "CODE_ENTITY", "ref": path, "lines": [node.lineno]}],
                        "AST",
                        0.95,
                        passed=passed,
                    )
                )
            elif '["' in text or "['" in text:
                m = re.search(r'\[["\'](\w+)["\']\]\s*==\s*["\'](\w+)["\']', text)
                if m:
                    desc = f"Test asserts body[{m.group(1)!r}] == {m.group(2)!r} in {path}"
                    rows.append(
                        await add_behavior(
                            ObservedBehaviorKind.TEST_ASSERTED,
                            desc,
                            [path],
                            [{"type": "CODE_ENTITY", "ref": path, "lines": [node.lineno]}],
                            "AST",
                            0.9,
                        )
                    )
        return rows
