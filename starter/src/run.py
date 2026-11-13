"""Orchestrate Day 06 data ingestion, vector indexing, retrieval, and benchmark evaluation."""
import json
import os
import re
import sys
import time
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    from .chunking import by_paragraph, fixed_size
    from .embeddings import MyEmbedder
    from .evaluation import evaluate_query, summarize
    from .ingestion import load_pdf
    from .models import Chunk, DocumentPage
    from .store import PgVectorStore
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.chunking import by_paragraph, fixed_size
    from src.embeddings import MyEmbedder
    from src.evaluation import evaluate_query, summarize
    from src.ingestion import load_pdf
    from src.models import Chunk, DocumentPage
    from src.store import PgVectorStore


STARTER_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
PDF_PATH = STARTER_DIR / "data" / "NIST_AI_RMF_1.0.pdf"
BENCHMARK_PATH = REPO_ROOT / "benchmark" / "questions.json"
DOCUMENT_ID = "nist-ai-rmf-1.0"
SOURCE_LABEL = "starter/data/NIST_AI_RMF_1.0.pdf"


def _compute_chunk_stats(chunks: list[Chunk]) -> dict[str, Any]:
    lengths = sorted(len(c.text) for c in chunks)
    n = len(lengths)
    if n == 0:
        return {"count": 0, "total_chars": 0, "min": 0, "median": 0, "p90": 0, "max": 0}
    return {
        "count": n,
        "total_chars": sum(lengths),
        "min": lengths[0],
        "median": lengths[n // 2],
        "p90": lengths[min(int(n * 0.9), n - 1)],
        "max": lengths[-1],
        "mean": round(sum(lengths) / n, 1),
    }


def _verify_benchmark_evidence(pages: list[DocumentPage], questions: list[dict[str, Any]]) -> None:
    page_map = {p.page: re.sub(r"\s+", " ", p.text).strip() for p in pages}
    for q in questions:
        gold_page = int(q["gold_page"])
        if gold_page not in page_map:
            raise ValueError(f"Question {q['id']} references missing page {gold_page}")
        quotes = [q["evidence_quote"], *(q.get("supporting_evidence") or [])]
        for index, quote in enumerate(quotes, start=1):
            quote_norm = re.sub(r"\s+", " ", quote).strip()
            if quote_norm not in page_map[gold_page]:
                raise ValueError(
                    f"Evidence quote {index} for {q['id']} not found on normalized page {gold_page}"
                )


def _extract_coherence_samples(
    pages: list[DocumentPage],
    chunks_a: list[Chunk],
    chunks_b: list[Chunk],
) -> list[dict[str, Any]]:
    """Select 10 deterministic source positions from the first 10 content pages (p06-p15)."""
    samples: list[dict[str, Any]] = []
    first_ten_pages = sorted(pages, key=lambda p: p.page)[:10]

    for page in first_ten_pages:
        paragraphs = [p.strip() for p in page.text.split("\n\n") if len(p.strip()) >= 120]
        target_para = paragraphs[0] if paragraphs else page.text.strip()
        # Use a mid-paragraph anchor slice so boundary effects are visible.
        anchor = target_para[:100]

        a_matches = [
            {"chunk_id": c.chunk_id, "char_length": len(c.text), "text": c.text}
            for c in chunks_a
            if c.page == page.page and (anchor[:40] in c.text or c.text[:40] in target_para)
        ]
        b_matches = [
            {"chunk_id": c.chunk_id, "char_length": len(c.text), "text": c.text}
            for c in chunks_b
            if c.page == page.page and (anchor[:40] in c.text or c.text[:40] in target_para)
        ]
        samples.append(
            {
                "page": page.page,
                "document_page": page.metadata.get("document_page"),
                "section": page.metadata.get("section"),
                "target_excerpt": target_para[:300],
                "strategy_A_chunks": a_matches,
                "strategy_B_C_chunks": b_matches,
            }
        )
    return samples


def _write_json_outputs(filename: str, data: Any) -> None:
    out_dir = REPO_ROOT / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / filename).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    run_started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    load_dotenv(STARTER_DIR / ".env")
    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is missing in starter/.env")

    print("Step 1: Loading and normalizing PDF corpus...")
    pages = load_pdf(
        path=PDF_PATH,
        document_id=DOCUMENT_ID,
        source=SOURCE_LABEL,
        log_path=REPO_ROOT / "results" / "ingestion_log.json",
    )

    if len(pages) < 30:
        raise RuntimeError(f"Expected at least 30 content pages, got {len(pages)}")
    print(f"Loaded {len(pages)} content pages.")

    print("Step 2: Loading and verifying benchmark questions...")
    questions = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    _verify_benchmark_evidence(pages, questions)
    print(f"Verified {len(questions)} benchmark questions against normalized source pages.")

    print("Step 3: Generating chunks for strategies A, B, and C...")
    chunks_a = [c for p in pages for c in fixed_size(p, size=500, overlap=50)]
    chunks_b = [c for p in pages for c in by_paragraph(p, max_size=800)]
    chunks_c = chunks_b

    coherence_samples = _extract_coherence_samples(pages, chunks_a, chunks_b)
    _write_json_outputs("coherence_samples.json", coherence_samples)

    embedder = MyEmbedder()
    store = PgVectorStore(database_url=database_url, dimensions=embedder.dimensions)
    store.create_schema()

    print(f"Step 4: Embedding and indexing with {embedder.model_name} (dim={embedder.dimensions})...")

    # Strategy A ingest
    t0 = time.perf_counter()
    tokens_before = embedder.total_tokens
    vectors_a = embedder.embed_documents([c.text for c in chunks_a])
    upsert_a = store.upsert("A", chunks_a, vectors_a)
    time_a = round(time.perf_counter() - t0, 3)
    tokens_a = embedder.total_tokens - tokens_before

    # Idempotency check: re-upsert Strategy A and confirm row count stays unchanged.
    count_a_first = store.count_chunks("A", DOCUMENT_ID)
    store.upsert("A", chunks_a, vectors_a)
    count_a_second = store.count_chunks("A", DOCUMENT_ID)
    if count_a_first != count_a_second:
        raise RuntimeError(
            f"Idempotency check failed for Strategy A: {count_a_first} != {count_a_second}"
        )

    # Strategy B ingest
    t0 = time.perf_counter()
    tokens_before = embedder.total_tokens
    vectors_b = embedder.embed_documents([c.text for c in chunks_b])
    upsert_b = store.upsert("B", chunks_b, vectors_b)
    time_b = round(time.perf_counter() - t0, 3)
    tokens_b = embedder.total_tokens - tokens_before

    # Strategy C ingest (reuses identical B chunk vectors in separate strategy partition C)
    t0 = time.perf_counter()
    upsert_c = store.upsert("C", chunks_c, vectors_b)
    time_c = round(time.perf_counter() - t0, 3)

    strategy_stats = {
        "run_started_at": run_started_at,
        "runtime_versions": {
            "python": sys.version.split()[0],
            "pypdf": version("pypdf"),
            "psycopg": version("psycopg"),
            "python_dotenv": version("python-dotenv"),
        },
        "embedding_model": embedder.model_name,
        "dimensions": embedder.dimensions,
        "vector_store": "PostgreSQL 16 + pgvector 0.8.7",
        "similarity_metric": "cosine (exact sequential scan)",
        "idempotency_check_strategy_A": {
            "count_after_first_upsert": count_a_first,
            "count_after_second_upsert": count_a_second,
            "duplicate_free": count_a_first == count_a_second,
        },
        "strategies": {
            "A": {
                "description": "fixed_size(size=500, overlap=50), no metadata filter",
                "chunk_stats": _compute_chunk_stats(chunks_a),
                "upsert_result": upsert_a,
                "ingest_seconds": time_a,
                "embedding_tokens": tokens_a,
                "embedding_cost_usd": round((tokens_a / 1_000_000.0) * 0.02, 6),
            },
            "B": {
                "description": "by_paragraph(max_size=800), no metadata filter",
                "chunk_stats": _compute_chunk_stats(chunks_b),
                "upsert_result": upsert_b,
                "ingest_seconds": time_b,
                "embedding_tokens": tokens_b,
                "embedding_cost_usd": round((tokens_b / 1_000_000.0) * 0.02, 6),
            },
            "C": {
                "description": "by_paragraph(max_size=800) with section metadata filter when question specifies filter",
                "chunk_stats": _compute_chunk_stats(chunks_c),
                "upsert_result": upsert_c,
                "ingest_seconds_db_only": time_c,
                "embedding_tokens_reused_from_B": tokens_b,
                "embedding_cost_usd_if_standalone": round((tokens_b / 1_000_000.0) * 0.02, 6),
            },
        },
    }

    print("Step 5: Embedding benchmark queries and running retrieval...")
    query_tokens_before = embedder.total_tokens
    query_vectors = {q["id"]: embedder.embed_query(q["question"]) for q in questions}
    query_tokens = embedder.total_tokens - query_tokens_before

    strategy_stats["query_embedding_tokens"] = query_tokens
    strategy_stats["total_api_tokens"] = embedder.total_tokens
    strategy_stats["total_api_cost_usd"] = round(embedder.estimated_cost_usd, 6)
    _write_json_outputs("strategy_stats.json", strategy_stats)

    traces: list[dict[str, Any]] = []
    for strategy in ("A", "B", "C"):
        for q in questions:
            applied_filter = q.get("filter") if strategy == "C" else None
            hits = store.search(
                strategy=strategy,
                query_vector=query_vectors[q["id"]],
                top_k=3,
                filters=applied_filter,
            )
            trace = evaluate_query(
                question=q,
                hits=hits,
                strategy=strategy,
                applied_filter=applied_filter,
            )
            traces.append(trace)

    _write_json_outputs("traces.json", traces)
    summary = summarize(traces)
    _write_json_outputs("metrics_summary.json", summary)
    strategy_stats["run_completed_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    _write_json_outputs("strategy_stats.json", strategy_stats)

    print("Step 6: Retrieval metrics summary (dev / test):")
    for strategy in ("A", "B", "C"):
        for split in ("dev", "test"):
            row = summary[strategy][split]
            print(
                f"  Strategy {strategy} [{split:4s}]: "
                f"Hit@1={row['hit_at_1_count']}/{row['total']} ({row['hit_at_1_rate']:.2%}) | "
                f"Hit@3={row['hit_at_3_count']}/{row['total']} ({row['hit_at_3_rate']:.2%}) | "
                f"Filter={row['filter_compliant_count']}/{row['filter_total']}"
            )
    print(
        f"Total tokens: {embedder.total_tokens} | Total cost USD: {embedder.estimated_cost_usd:.6f}"
    )


if __name__ == "__main__":
    main()
