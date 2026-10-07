from __future__ import annotations

import re
import uuid
from collections import Counter
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.commands.context import CommandContext
from core.domain.canonical_json import sha256_hex
from core.domain.delivery_cycles.models import DeliveryCycle
from core.domain.enums import KnowledgeClass, KnowledgeItemStatus
from core.domain.events.append import append_domain_event
from core.domain.repositories.models import Repository, RepositoryWorkspace
from core.intelligence.brownfield.models import RepositoryDiscovery
from core.intelligence.repository.frameworks import detect_frameworks
from core.intelligence.repository.git_source import GitSourceReader
from core.intelligence.repository.manifests import parse_pyproject, parse_requirements
from core.product_model.models import KnowledgeItem
from core.repositories.workspace_locator import WorkspaceLocator


class RepositoryDiscoveryService:
    async def discover(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        delivery_cycle_id: uuid.UUID,
        sha: str,
        ctx: CommandContext,
    ) -> RepositoryDiscovery:
        repo = await session.get(Repository, repository_id)
        cycle = await session.get(DeliveryCycle, delivery_cycle_id)
        if repo is None or cycle is None or repo.workspace_id is None:
            raise ValueError("repository or cycle missing")
        ws = await session.get(RepositoryWorkspace, repo.workspace_id)
        if ws is None:
            raise ValueError("workspace missing")
        git_dir = str(WorkspaceLocator().resolve(ws.storage_backend, ws.logical_location))
        reader = GitSourceReader(git_dir)
        reader.ensure_commit(sha)
        entries = reader.list_tree(sha)
        manifests: list[dict[str, Any]] = []
        dependencies: list[dict[str, str | None]] = []
        imports: list[str] = []
        config_files: list[str] = []
        entry_points: list[str] = []
        lang_counter: Counter[str] = Counter()
        sample_source = ""
        for entry in entries:
            ext = entry.path.rsplit(".", 1)[-1].lower() if "." in entry.path else ""
            if ext == "py":
                lang_counter["python"] += 1
            elif ext in {"md", "yaml", "yml", "toml", "json"}:
                lang_counter[ext] += 1
            base = entry.path.rsplit("/", 1)[-1]
            if base == "pyproject.toml":
                text = reader.read_file_at_commit(sha, entry.path)
                if text:
                    parsed = parse_pyproject(text.decode("utf-8", errors="replace"), entry.path)
                    manifests.append({"path": entry.path, "name": parsed.name})
                    for name, ver in parsed.dependencies:
                        dependencies.append({"name": name, "version": ver})
            elif base.startswith("requirements") and base.endswith(".txt"):
                text = reader.read_file_at_commit(sha, entry.path)
                if text:
                    parsed = parse_requirements(text.decode("utf-8", errors="replace"), entry.path)
                    manifests.append({"path": entry.path, "name": parsed.name})
                    for name, ver in parsed.dependencies:
                        dependencies.append({"name": name, "version": ver})
            elif base in {"setup.cfg", "pytest.ini", ".env.example"}:
                config_files.append(entry.path)
            if entry.path.endswith(".py") and len(sample_source) < 50_000:
                blob = reader.read_file_at_commit(sha, entry.path)
                if blob:
                    sample_source += blob.decode("utf-8", errors="replace")[:5000]
                    for m in re.finditer(r"^(?:from|import)\s+([\w.]+)", blob.decode(), re.M):
                        imports.append(m.group(1))
        for entry in entries:
            if not entry.path.endswith("main.py"):
                continue
            text = reader.read_file_at_commit(sha, entry.path)
            if text and "FastAPI(" in text.decode("utf-8", errors="replace"):
                entry_points.append(f"{entry.path}:app")
        git_meta = reader.file_churn_stats(sha, limit=10)
        content: dict[str, Any] = {
            "file_count": len(entries),
            "languages": dict(lang_counter),
            "manifests": manifests,
            "dependencies": dependencies,
            "frameworks": detect_frameworks(
                [(str(d["name"]), d.get("version")) for d in dependencies if d.get("name")],
                imports,
                sample_source,
            ),
            "entry_points": entry_points,
            "config_files": config_files,
            "git": {
                "head_sha": sha,
                "default_branch": repo.default_branch,
                "top_churn": git_meta,
            },
        }
        content_hash = sha256_hex(content)
        row = RepositoryDiscovery(
            repository_id=repository_id,
            delivery_cycle_id=delivery_cycle_id,
            commit_sha=sha,
            content=content,
            content_hash=content_hash,
        )
        session.add(row)
        await session.flush()
        for fw in content["frameworks"]:
            await self._fact_item(
                session,
                cycle.project_id,
                delivery_cycle_id,
                f"Framework detected: {fw}",
                [{"type": "DISCOVERY", "ref": str(row.id)}],
                ctx,
            )
        dep_names = sorted({str(d["name"]) for d in dependencies if d.get("name")})
        for stmt in (
            f"Repository summary: config_files = {config_files!r}",
            f"Repository summary: entry_points = {entry_points!r}",
            f"Repository summary: dependencies = {dep_names!r}",
            f"Repository summary: file_count = {len(entries)}",
        ):
            await self._fact_item(
                session,
                cycle.project_id,
                delivery_cycle_id,
                stmt,
                [{"type": "DISCOVERY", "ref": str(row.id)}],
                ctx,
            )
        await append_domain_event(
            session,
            aggregate_type="repository_discovery",
            aggregate_id=row.id,
            event_type="repository.discovered",
            payload={"commit_sha": sha, "content_hash": content_hash},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=cycle.project_id,
            delivery_cycle_id=delivery_cycle_id,
        )
        return row

    async def _fact_item(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        delivery_cycle_id: uuid.UUID,
        statement: str,
        evidence_refs: list[dict[str, str]],
        ctx: CommandContext,
    ) -> KnowledgeItem:
        item = KnowledgeItem(
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
            knowledge_class=KnowledgeClass.FACT,
            statement=statement,
            provenance={"origin": "DETERMINISTIC", "source": "repository_discovery"},
            evidence_refs=evidence_refs,
            status=KnowledgeItemStatus.ACTIVE,
        )
        session.add(item)
        await session.flush()
        await append_domain_event(
            session,
            aggregate_type="knowledge_item",
            aggregate_id=item.id,
            event_type="knowledge_item.created",
            payload={"class": KnowledgeClass.FACT.value},
            actor_id=ctx.actor.id,
            correlation_id=ctx.correlation_id,
            project_id=project_id,
            delivery_cycle_id=delivery_cycle_id,
        )
        return item
