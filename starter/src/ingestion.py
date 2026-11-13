"""Read and normalize source data from PDF documents."""
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import pypdf

from .models import DocumentPage

EXCLUDED_PHYSICAL_PAGES = {1, 2, 3, 4, 5, 48}
HEADER_PREFIX = "NIST AI 100-1 AI RMF 1.0"


def get_section_for_page(physical_page: int) -> str:
    """Map physical PDF page number to its verified NIST AI RMF section."""
    if 6 <= physical_page <= 8:
        return "executive_summary"
    if 9 <= physical_page <= 24:
        return "part_1_foundational"
    if 25 <= physical_page <= 39:
        return "part_2_core_profiles"
    if 40 <= physical_page <= 47:
        return "appendix"
    return "front_or_back_matter"


def _is_standalone_heading(line: str) -> bool:
    """Identify standalone headings that should not merge with following lines."""
    patterns = (
        r"^Executive Summary\b",
        r"^Part \d+:",
        r"^Appendix [A-D]:?$",
        r"^Table \d+:",
        r"^Fig\. \d+\.",
        r"^\d+(\.\d+)*\s+[A-Z][A-Za-z0-9\s,\-–]+$",
        r"^Categories\s+Subcategories\b",
    )
    return any(re.match(pat, line) for pat in patterns)


def _starts_new_block(line: str) -> bool:
    """Identify lines that begin a new bullet or RMF category/subcategory item."""
    patterns = (
        r"^(GOVERN|MAP|MEASURE|MANAGE)\s+\d+(\.\d+)?:",
        r"^[•\-\*]\s+",
        r"^\d+\.\s+[A-Z]",
    )
    return any(re.match(pat, line) for pat in patterns)


def normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace while keeping paragraph structure."""
    cleaned = unicodedata.normalize("NFC", text or "")
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"([A-Za-z])-\n([A-Za-z])", r"\1\2", cleaned)

    raw_lines = [re.sub(r"[ \t]+", " ", line).strip() for line in cleaned.split("\n")]
    lines = [line for line in raw_lines if line and line != HEADER_PREFIX]

    if lines and re.fullmatch(r"(?:Page\s+)?\d{1,2}|[ivx]+", lines[-1]):
        lines.pop()

    paragraphs: list[str] = []
    buffer: list[str] = []

    def flush_buffer() -> None:
        if buffer:
            paragraphs.append(" ".join(buffer))
            buffer.clear()

    for line in lines:
        if _is_standalone_heading(line):
            flush_buffer()
            paragraphs.append(line)
            continue

        if _starts_new_block(line):
            flush_buffer()
            buffer.append(line)
            continue

        if buffer:
            prev = buffer[-1]
            if prev.endswith((".", ":", "?", "!")) and len(prev) < 68:
                flush_buffer()
        buffer.append(line)

    flush_buffer()
    return "\n\n".join(paragraphs)


def load_pdf(
    path: Path,
    document_id: str,
    source: str,
    log_path: Path | None = None,
) -> list[DocumentPage]:
    """Extract content pages from PDF, keep page traceability, and log errors/exclusions."""
    if not path.exists():
        raise FileNotFoundError(f"Source PDF not found: {path}")

    reader = pypdf.PdfReader(str(path))
    pages: list[DocumentPage] = []
    log_records: list[dict[str, Any]] = []

    for index, pdf_page in enumerate(reader.pages):
        physical_page = index + 1
        raw_text = pdf_page.extract_text() or ""

        if physical_page in EXCLUDED_PHYSICAL_PAGES:
            log_records.append(
                {
                    "physical_page": physical_page,
                    "status": "excluded",
                    "reason": "front_or_back_matter",
                    "raw_chars": len(raw_text.strip()),
                }
            )
            continue

        normalized = normalize_text(raw_text)
        if not normalized:
            log_records.append(
                {
                    "physical_page": physical_page,
                    "status": "error_empty_text",
                    "reason": "no_extractable_text_ocr_needed",
                    "raw_chars": 0,
                }
            )
            continue

        section = get_section_for_page(physical_page)
        document_page = physical_page - 5
        metadata = {
            "section": section,
            "document_page": document_page,
            "year": 2023,
            "version": "1.0",
        }
        pages.append(
            DocumentPage(
                document_id=document_id,
                source=source,
                page=physical_page,
                text=normalized,
                metadata=metadata,
            )
        )
        log_records.append(
            {
                "physical_page": physical_page,
                "document_page": document_page,
                "section": section,
                "status": "ingested",
                "raw_chars": len(raw_text.strip()),
                "normalized_chars": len(normalized),
            }
        )

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "document_id": document_id,
            "source": source,
            "total_physical_pages": len(reader.pages),
            "ingested_pages": len(pages),
            "excluded_pages": sum(1 for r in log_records if r["status"] == "excluded"),
            "error_pages": sum(1 for r in log_records if r["status"].startswith("error")),
            "pages": log_records,
        }
        log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return pages
