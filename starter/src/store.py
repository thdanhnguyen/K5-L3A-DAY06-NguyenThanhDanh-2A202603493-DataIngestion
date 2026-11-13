"""PostgreSQL + pgvector persistent vector store with metadata filtering."""
import json
from typing import Any

import psycopg

from .models import Chunk

ALLOWED_FILTER_COLUMNS = {"document_id", "page", "section", "source"}


def _vector_literal(vector: list[float]) -> str:
    """Format a float list into pgvector text syntax."""
    return "[" + ",".join(f"{v:.8f}" for v in vector) + "]"


class PgVectorStore:
    """Persistent vector store backed by PostgreSQL and pgvector."""

    def __init__(self, database_url: str, dimensions: int) -> None:
        if not database_url:
            raise ValueError("database_url must not be empty")
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.database_url = database_url
        self.dimensions = dimensions
        self.table_name = "rag_chunks"

    def create_schema(self) -> None:
        """Create vector extension, chunk table, and metadata indexes."""
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self.table_name} (
                        strategy TEXT NOT NULL,
                        chunk_id TEXT NOT NULL,
                        document_id TEXT NOT NULL,
                        source TEXT NOT NULL,
                        page INTEGER NOT NULL,
                        section TEXT NOT NULL,
                        text TEXT NOT NULL,
                        metadata JSONB NOT NULL,
                        embedding vector({self.dimensions}) NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        PRIMARY KEY (strategy, chunk_id)
                    );
                    """
                )
                cur.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_{self.table_name}_strategy_section
                    ON {self.table_name} (strategy, section);
                    """
                )
            conn.commit()

    def count_chunks(self, strategy: str, document_id: str | None = None) -> int:
        """Return stored chunk count for a strategy (and optional document_id)."""
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                if document_id is None:
                    cur.execute(
                        f"SELECT COUNT(*) FROM {self.table_name} WHERE strategy = %s;",
                        (strategy,),
                    )
                else:
                    cur.execute(
                        f"SELECT COUNT(*) FROM {self.table_name} WHERE strategy = %s AND document_id = %s;",
                        (strategy, document_id),
                    )
                row = cur.fetchone()
                return int(row[0]) if row else 0

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> dict[str, int]:
        """Upsert chunks idempotently and prune obsolete chunks for updated documents."""
        if len(chunks) != len(vectors):
            raise ValueError(
                f"chunks ({len(chunks)}) and vectors ({len(vectors)}) length mismatch"
            )
        for vec in vectors:
            if len(vec) != self.dimensions:
                raise ValueError(
                    f"vector dimension {len(vec)} does not match store dimension {self.dimensions}"
                )

        if not chunks:
            return {"upserted": 0, "pruned": 0}

        doc_ids = sorted({c.document_id for c in chunks})
        active_ids = [c.chunk_id for c in chunks]
        pruned = 0

        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                for doc_id in doc_ids:
                    cur.execute(
                        f"""
                        DELETE FROM {self.table_name}
                        WHERE strategy = %s AND document_id = %s AND NOT (chunk_id = ANY(%s));
                        """,
                        (strategy, doc_id, active_ids),
                    )
                    pruned += cur.rowcount or 0

                sql = f"""
                    INSERT INTO {self.table_name}
                        (strategy, chunk_id, document_id, source, page, section, text, metadata, embedding)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::vector)
                    ON CONFLICT (strategy, chunk_id) DO UPDATE SET
                        document_id = EXCLUDED.document_id,
                        source = EXCLUDED.source,
                        page = EXCLUDED.page,
                        section = EXCLUDED.section,
                        text = EXCLUDED.text,
                        metadata = EXCLUDED.metadata,
                        embedding = EXCLUDED.embedding,
                        updated_at = NOW();
                """
                rows = [
                    (
                        strategy,
                        chunk.chunk_id,
                        chunk.document_id,
                        chunk.source,
                        chunk.page,
                        str(chunk.metadata.get("section", "unknown")),
                        chunk.text,
                        json.dumps(chunk.metadata, ensure_ascii=False),
                        _vector_literal(vec),
                    )
                    for chunk, vec in zip(chunks, vectors)
                ]
                cur.executemany(sql, rows)
            conn.commit()

        return {"upserted": len(chunks), "pruned": pruned}

    def search(
        self,
        strategy: str,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Filter allowed metadata in SQL, rank by exact cosine distance, and return top-k."""
        if len(query_vector) != self.dimensions:
            raise ValueError(
                f"query_vector dimension {len(query_vector)} does not match {self.dimensions}"
            )

        qvec_lit = _vector_literal(query_vector)
        where_clauses = ["strategy = %s"]
        where_params: list[Any] = [strategy]

        if filters:
            for key, value in filters.items():
                if key not in ALLOWED_FILTER_COLUMNS:
                    raise ValueError(f"Unsupported metadata filter field: {key}")
                where_clauses.append(f"{key} = %s")
                where_params.append(value)

        where_sql = " AND ".join(where_clauses)
        sql = f"""
            SELECT
                chunk_id,
                document_id,
                source,
                page,
                section,
                text,
                metadata,
                1 - (embedding <=> %s::vector) AS cosine_similarity
            FROM {self.table_name}
            WHERE {where_sql}
            ORDER BY embedding <=> %s::vector ASC
            LIMIT %s;
        """
        params: list[Any] = [qvec_lit] + where_params + [qvec_lit, top_k]

        results: list[dict[str, Any]] = []
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                for row in cur.fetchall():
                    meta = row[6] if isinstance(row[6], dict) else json.loads(row[6])
                    results.append(
                        {
                            "chunk_id": row[0],
                            "document_id": row[1],
                            "source": row[2],
                            "page": int(row[3]),
                            "section": row[4],
                            "text": row[5],
                            "metadata": meta,
                            "score": round(float(row[7]), 6),
                        }
                    )
        return results
