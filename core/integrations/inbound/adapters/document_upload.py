from __future__ import annotations

import io
import uuid
from typing import Any

from core.commands.context import CommandContext
from core.domain.actors.models import Actor
from core.domain.enums import ActorKind
from core.integrations.inbound.envelope import InboundEventEnvelope
from core.integrations.inbound.storage import ContentAddressedStore, sha256_text
from sqlalchemy.ext.asyncio import AsyncSession


def extract_text_from_bytes(raw: bytes, mime_type: str, filename: str) -> str:
    if mime_type in {"text/plain", "text/markdown"} or filename.endswith((".md", ".txt")):
        return raw.decode("utf-8", errors="replace")
    if filename.endswith(".docx") or mime_type == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ):
        from docx import Document

        doc = Document(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if filename.endswith(".pdf") or mime_type == "application/pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)
    return raw.decode("utf-8", errors="replace")


class DocumentUploadAdapter:
    source_type = "document_upload"

    async def authenticate(
        self,
        session: AsyncSession,
        raw: dict[str, Any],
        ctx: CommandContext | None,
    ) -> tuple[bool, str | None]:
        if ctx is None:
            return False, "UNAUTHENTICATED"
        actor = await session.get(Actor, ctx.actor.id)
        if actor is None:
            return False, "UNAUTHENTICATED"
        if actor.kind not in {ActorKind.HUMAN, ActorKind.INTEGRATION, ActorKind.SYSTEM}:
            return False, "UNAUTHORIZED"
        return True, None

    async def validate(self, session: AsyncSession, raw: dict[str, Any]) -> tuple[bool, str | None]:
        if raw.get("json_body"):
            body = raw["json_body"]
            if not body.get("title") or not body.get("text"):
                return False, "JSON requires title and text"
            return True, None
        if raw.get("file_bytes") is None:
            return False, "file or JSON body required"
        name = str(raw.get("filename", "upload.txt"))
        if not any(name.endswith(ext) for ext in (".md", ".txt", ".pdf", ".docx")):
            return False, "unsupported file type"
        return True, None

    async def normalize(self, session: AsyncSession, raw: dict[str, Any]) -> InboundEventEnvelope:
        project_id = str(raw["project_id"])
        event_id = str(raw.get("event_id") or raw.get("idempotency_key") or uuid.uuid4())
        source_id = str(raw.get("source_id") or project_id)
        if raw.get("json_body"):
            body = raw["json_body"]
            text = str(body["text"])
            title = str(body["title"])
            mime = "text/plain"
            file_bytes = text.encode("utf-8")
            filename = f"{title}.txt"
        else:
            file_bytes = raw["file_bytes"]
            filename = str(raw.get("filename", "upload.md"))
            mime = str(raw.get("mime_type", "text/plain"))
            title = str(raw.get("title") or filename)
            text = extract_text_from_bytes(file_bytes, mime, filename)

        store = ContentAddressedStore()
        storage_ref, content_hash = store.put_bytes(file_bytes, prefix="product_sources/raw")
        text_hash = sha256_text(text)
        normalized = {
            "title": title,
            "mime_type": mime,
            "filename": filename,
            "text": text,
            "text_hash": text_hash,
            "raw_storage_ref": storage_ref,
            "content_hash": content_hash,
            "source_type_label": str(raw.get("source_type_label", "PRD")),
            "lineage_key": str(raw.get("lineage_key", "default")),
            "delivery_cycle_id": raw.get("delivery_cycle_id"),
        }
        envelope = InboundEventEnvelope(
            source_type=self.source_type,
            source_id=source_id,
            event_id=event_id,
            project_id=project_id,
            payload={"normalized_ref": storage_ref, "content_hash": content_hash},
        )
        raw["_normalized"] = normalized
        return envelope

    async def to_command(
        self,
        session: AsyncSession,
        envelope: InboundEventEnvelope,
        normalized: dict[str, Any],
    ) -> tuple[str, str, str, dict[str, Any]]:
        del session
        assert envelope.project_id is not None
        payload = {
            "project_id": envelope.project_id,
            "lineage_key": normalized["lineage_key"],
            "source_type": normalized["source_type_label"],
            "title": normalized["title"],
            "mime_type": normalized["mime_type"],
            "content_hash": normalized["content_hash"],
            "raw_storage_ref": normalized["raw_storage_ref"],
            "text": normalized["text"],
            "delivery_cycle_id": normalized.get("delivery_cycle_id"),
            "inbound_event_id": None,
        }
        return (
            "ingest_product_source",
            "project",
            envelope.project_id,
            payload,
        )
