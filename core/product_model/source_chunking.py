from __future__ import annotations

import re
from collections.abc import Callable

from core.product_model.schemas import ProductDecomposition

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")


def _dedupe_by_ref[T](items: list[T], ref_getter: Callable[[T], str]) -> list[T]:
    seen: set[str] = set()
    out: list[T] = []
    for item in items:
        ref = ref_getter(item)
        if ref in seen:
            continue
        seen.add(ref)
        out.append(item)
    return out


def chunk_markdown_by_headings(text: str, max_chars: int) -> list[str]:
    """Split markdown into chunks at heading boundaries, each at most *max_chars*."""
    if max_chars <= 0 or len(text) <= max_chars:
        return [text]

    lines = text.splitlines(keepends=True)
    sections: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            sections.append("".join(current))

    for line in lines:
        if _HEADING_RE.match(line.rstrip("\n")) and current:
            flush()
            current = [line]
        else:
            current.append(line)
    flush()

    if not sections:
        return _hard_split(text, max_chars)

    chunks: list[str] = []
    buf: list[str] = []
    buf_len = 0

    def flush_chunk() -> None:
        nonlocal buf_len
        if buf:
            chunks.append("".join(buf))
            buf.clear()
            buf_len = 0

    for section in sections:
        sec_len = len(section)
        if sec_len > max_chars:
            flush_chunk()
            chunks.extend(_hard_split(section, max_chars))
            continue
        if buf_len + sec_len > max_chars and buf:
            flush_chunk()
        buf.append(section)
        buf_len += sec_len
    flush_chunk()
    return chunks or [text]


def _hard_split(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        parts.append(text[start : start + max_chars])
        start += max_chars
    return parts


def merge_product_decompositions(
    left: ProductDecomposition,
    right: ProductDecomposition,
) -> ProductDecomposition:
    """Combine chunk-level proposals; first occurrence wins on duplicate refs."""
    questions = left.open_questions + right.open_questions
    seen_q: set[str] = set()
    merged_questions = []
    for q in questions:
        if q.question in seen_q:
            continue
        seen_q.add(q.question)
        merged_questions.append(q)

    assumptions: list[str] = []
    seen_a: set[str] = set()
    for a in left.assumptions + right.assumptions:
        if a in seen_a:
            continue
        seen_a.add(a)
        assumptions.append(a)

    return ProductDecomposition(
        capabilities=_dedupe_by_ref(left.capabilities + right.capabilities, lambda c: c.ref),
        features=_dedupe_by_ref(left.features + right.features, lambda f: f.ref),
        feature_specs=_dedupe_by_ref(left.feature_specs + right.feature_specs, lambda s: s.ref),
        requirements=_dedupe_by_ref(left.requirements + right.requirements, lambda r: r.ref),
        user_stories=_dedupe_by_ref(left.user_stories + right.user_stories, lambda s: s.ref),
        acceptance_criteria=_dedupe_by_ref(
            left.acceptance_criteria + right.acceptance_criteria, lambda a: a.ref
        ),
        open_questions=merged_questions,
        assumptions=assumptions,
    )
