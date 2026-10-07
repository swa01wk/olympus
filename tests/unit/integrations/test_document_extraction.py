from __future__ import annotations

import io

import pytest
from core.integrations.inbound.adapters.document_upload import extract_text_from_bytes


@pytest.mark.unit
def test_extract_text_plain_and_markdown() -> None:
    raw = b"# Title\n\nBody text"
    assert "Body text" in extract_text_from_bytes(raw, "text/markdown", "doc.md")


@pytest.mark.unit
def test_extract_text_pdf() -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    text = extract_text_from_bytes(buf.getvalue(), "application/pdf", "doc.pdf")
    assert isinstance(text, str)


@pytest.mark.unit
def test_extract_text_docx() -> None:
    from docx import Document

    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph("SupportDesk ticket rule")
    doc.save(buf)
    text = extract_text_from_bytes(buf.getvalue(), "application/octet-stream", "x.docx")
    assert "SupportDesk" in text
