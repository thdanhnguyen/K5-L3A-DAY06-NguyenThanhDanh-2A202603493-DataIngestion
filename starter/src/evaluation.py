"""Evaluate retrieved evidence and summarize Hit@1, Evidence Hit@3, and filter compliance."""
import re
from typing import Any


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _hit_matches_evidence(question: dict[str, Any], hit: dict[str, Any]) -> bool:
    """Check whether a retrieved chunk matches gold source/page and contains gold evidence."""
    gold_source = question["gold_source_id"]
    if hit.get("document_id") != gold_source:
        return False

    valid_pages = {int(question["gold_page"])}
    for alt_page in question.get("alt_gold_pages") or []:
        valid_pages.add(int(alt_page))

    if int(hit.get("page", -1)) not in valid_pages:
        return False

    chunk_norm = _norm_ws(hit.get("text", ""))
    quote_norm = _norm_ws(question.get("evidence_quote", ""))
    if quote_norm and quote_norm in chunk_norm:
        return True

    # Support checking verified key evidence spans when a fixed-size chunk captures
    # the core evidence clause without the full quote boundary.
    required_phrases = question.get("evidence_required_phrases") or []
    if required_phrases and all(_norm_ws(p) in chunk_norm for p in required_phrases):
        return True

    return False


def _hit_complies_filter(filters: dict[str, Any] | None, hit: dict[str, Any]) -> bool:
    if not filters:
        return True
    meta = hit.get("metadata") or {}
    for key, expected in filters.items():
        actual = hit.get(key, meta.get(key))
        if actual != expected:
            return False
    return True


def evaluate_query(
    question: dict[str, Any],
    hits: list[dict[str, Any]],
    strategy: str = "",
    applied_filter: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate top-k retrieval hits for a single benchmark question."""
    hit_flags = [_hit_matches_evidence(question, h) for h in hits]
    hit_at_1 = bool(hit_flags[0]) if hit_flags else False
    hit_at_3 = any(hit_flags[:3])

    q_filter = question.get("filter")
    filter_compliant: bool | None = None
    if q_filter:
        filter_compliant = bool(hits) and all(_hit_complies_filter(q_filter, h) for h in hits)

    annotated_hits = []
    for rank, (hit, is_match) in enumerate(zip(hits, hit_flags), start=1):
        annotated_hits.append(
            {
                "rank": rank,
                "chunk_id": hit["chunk_id"],
                "document_id": hit["document_id"],
                "source": hit["source"],
                "page": hit["page"],
                "section": hit.get("section") or (hit.get("metadata") or {}).get("section"),
                "score": hit["score"],
                "evidence_match": is_match,
                "text": hit["text"],
                "metadata": hit["metadata"],
            }
        )

    return {
        "strategy": strategy,
        "question_id": question["id"],
        "split": question["split"],
        "type": question.get("type", ""),
        "question": question["question"],
        "gold_source_id": question["gold_source_id"],
        "gold_page": question["gold_page"],
        "evidence_quote": question["evidence_quote"],
        "supporting_evidence": question.get("supporting_evidence") or [],
        "question_filter": q_filter,
        "applied_filter": applied_filter,
        "hit_at_1": hit_at_1,
        "hit_at_3": hit_at_3,
        "filter_compliant": filter_compliant,
        "hits": annotated_hits,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate Hit@1, Evidence Hit@3, and filter compliance by strategy and split."""
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for trace in traces:
        key = (trace["strategy"], trace["split"])
        grouped.setdefault(key, []).append(trace)

    summary: dict[str, Any] = {}
    for (strategy, split), items in sorted(grouped.items()):
        total = len(items)
        hit1 = sum(1 for item in items if item["hit_at_1"])
        hit3 = sum(1 for item in items if item["hit_at_3"])
        filter_items = [item for item in items if item["question_filter"] is not None]
        filter_ok = sum(1 for item in filter_items if item["filter_compliant"])

        summary.setdefault(strategy, {})[split] = {
            "total": total,
            "hit_at_1_count": hit1,
            "hit_at_1_rate": round(hit1 / total, 4) if total else 0.0,
            "hit_at_3_count": hit3,
            "hit_at_3_rate": round(hit3 / total, 4) if total else 0.0,
            "filter_total": len(filter_items),
            "filter_compliant_count": filter_ok,
            "filter_compliant_rate": (
                round(filter_ok / len(filter_items), 4) if filter_items else None
            ),
        }

    return summary
