"""Deterministic candidate commit ordering for integration merges."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from core.repositories.git_inspect import GitInspector


@dataclass(frozen=True)
class OrderedCandidate:
    task_id: uuid.UUID
    task_key: str
    candidate_commit_id: uuid.UUID
    candidate_commit_sha: str
    position: int
    included: bool
    skip_reason: str | None = None


def topological_order_task_ids(
    task_ids: set[uuid.UUID],
    edges: list[tuple[uuid.UUID, uuid.UUID]],
    key_by_id: dict[uuid.UUID, str],
) -> list[uuid.UUID]:
    """Topological sort of task DAG; tie-break by task key."""
    incoming: dict[uuid.UUID, set[uuid.UUID]] = {tid: set() for tid in task_ids}
    outgoing: dict[uuid.UUID, set[uuid.UUID]] = {tid: set() for tid in task_ids}
    for task_id, dep_id in edges:
        if task_id not in task_ids or dep_id not in task_ids:
            continue
        incoming[task_id].add(dep_id)
        outgoing[dep_id].add(task_id)
    ready = sorted([tid for tid in task_ids if not incoming[tid]], key=lambda t: key_by_id[t])
    ordered: list[uuid.UUID] = []
    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for child in sorted(outgoing[current], key=lambda t: key_by_id[t]):
            incoming[child].remove(current)
            if not incoming[child]:
                ready.append(child)
        ready.sort(key=lambda t: key_by_id[t])
    if len(ordered) != len(task_ids):
        raise ValueError("task dependency cycle detected")
    return ordered


def order_candidates(
    *,
    git_dir_path: str,
    base_sha: str,
    entries: list[tuple[uuid.UUID, str, uuid.UUID, str]],
    dependency_edges: list[tuple[uuid.UUID, uuid.UUID]],
) -> list[OrderedCandidate]:
    """
    Order candidate commits by task DAG (key tie-break) and skip commits already
    ancestral to the merge base or prior candidates in the sequence.
    """
    if not entries:
        return []
    task_ids = {e[0] for e in entries}
    key_by_id = {e[0]: e[1] for e in entries}
    sha_by_task = {e[0]: e[3] for e in entries}
    commit_id_by_task = {e[0]: e[2] for e in entries}
    task_order = topological_order_task_ids(task_ids, dependency_edges, key_by_id)
    inspector = GitInspector()
    from pathlib import Path

    path = Path(git_dir_path)
    merged_head = base_sha
    result: list[OrderedCandidate] = []
    for position, task_id in enumerate(task_order):
        sha = sha_by_task[task_id]
        skip_reason: str | None = None
        included = True
        if inspector.is_ancestor(path, sha, merged_head):
            included = False
            skip_reason = "ALREADY_ANCESTOR"
        else:
            merged_head = sha
        result.append(
            OrderedCandidate(
                task_id=task_id,
                task_key=key_by_id[task_id],
                candidate_commit_id=commit_id_by_task[task_id],
                candidate_commit_sha=sha,
                position=position,
                included=included,
                skip_reason=skip_reason,
            )
        )
    return result
