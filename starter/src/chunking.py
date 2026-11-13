"""Implement fixed-size and structure-aware chunking."""
import re

from .models import Chunk, DocumentPage


def _build_chunk(
    page: DocumentPage,
    strategy_tag: str,
    index: int,
    text: str,
) -> Chunk:
    """Create a Chunk instance with traceable metadata."""
    chunk_meta = dict(page.metadata)
    chunk_meta["chunk_strategy"] = strategy_tag
    chunk_meta["chunk_index"] = index
    chunk_meta["char_length"] = len(text)
    return Chunk(
        chunk_id=f"{page.document_id}-p{page.page:02d}-{strategy_tag}-{index:02d}",
        document_id=page.document_id,
        source=page.source,
        page=page.page,
        text=text,
        metadata=chunk_meta,
    )


def fixed_size(page: DocumentPage, size: int = 500, overlap: int = 50) -> list[Chunk]:
    """Split normalized page text into fixed-size overlapping character windows."""
    if size <= 0:
        raise ValueError("size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must satisfy 0 <= overlap < size")

    text = page.text.strip()
    if not text:
        return []

    chunks: list[Chunk] = []
    step = size - overlap
    start = 0
    idx = 0
    length = len(text)

    while start < length:
        end = min(start + size, length)
        window = text[start:end].strip()
        if window:
            chunks.append(_build_chunk(page, "fix", idx, window))
            idx += 1
        if end >= length:
            break
        start += step

    return chunks


def _split_oversized_paragraph(paragraph: str, max_size: int) -> list[str]:
    """Split an oversized paragraph by sentence boundaries, or by words if needed."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", paragraph) if s.strip()]
    if len(sentences) <= 1:
        # Fallback to word-level splitting so no word is cut in half.
        words = paragraph.split()
        parts: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip() if current else word
            if len(candidate) <= max_size:
                current = candidate
            else:
                if current:
                    parts.append(current)
                current = word
        if current:
            parts.append(current)
        return parts

    parts = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_size:
            if current:
                parts.append(current)
                current = ""
            parts.extend(_split_oversized_paragraph(sentence, max_size))
            continue

        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_size:
            current = candidate
        else:
            if current:
                parts.append(current)
            current = sentence
    if current:
        parts.append(current)
    return parts


def by_paragraph(page: DocumentPage, max_size: int = 800) -> list[Chunk]:
    """Group consecutive paragraphs up to max_size and split oversized paragraphs."""
    if max_size <= 0:
        raise ValueError("max_size must be positive")

    raw_paragraphs = [p.strip() for p in page.text.split("\n\n") if p.strip()]
    if not raw_paragraphs:
        return []

    expanded: list[str] = []
    for para in raw_paragraphs:
        if len(para) <= max_size:
            expanded.append(para)
        else:
            expanded.extend(_split_oversized_paragraph(para, max_size))

    chunks: list[Chunk] = []
    current = ""
    idx = 0

    for para in expanded:
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= max_size:
            current = candidate
        else:
            if current:
                chunks.append(_build_chunk(page, "par", idx, current))
                idx += 1
            current = para

    if current:
        chunks.append(_build_chunk(page, "par", idx, current))

    return chunks
