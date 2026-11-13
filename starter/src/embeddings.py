"""OpenAI embedding adapter using real API requests without mock fallback."""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol

from dotenv import load_dotenv

DEFAULT_MODEL = "text-embedding-3-small"
MODEL_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}
PRICE_PER_MILLION_TOKENS_USD = {
    "text-embedding-3-small": 0.02,
    "text-embedding-3-large": 0.13,
    "text-embedding-ada-002": 0.10,
}


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class MyEmbedder:
    """Embedding adapter calling OpenAI Embeddings API directly."""

    def __init__(self, model_name: str | None = None, batch_size: int = 64) -> None:
        env_path = Path(__file__).resolve().parents[1] / ".env"
        if env_path.exists():
            load_dotenv(env_path)

        resolved_model = (model_name or os.getenv("EMBEDDING_MODEL") or DEFAULT_MODEL).strip()
        self.model_name = resolved_model or DEFAULT_MODEL
        if self.model_name not in MODEL_DIMENSIONS:
            raise ValueError(f"Unsupported embedding model: {self.model_name}")

        self.dimensions = MODEL_DIMENSIONS[self.model_name]
        self.api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is missing in starter/.env or environment.")

        self.batch_size = batch_size
        self.endpoint = "https://api.openai.com/v1/embeddings"
        self.total_tokens = 0
        self.total_requests = 0

    @property
    def estimated_cost_usd(self) -> float:
        rate = PRICE_PER_MILLION_TOKENS_USD.get(self.model_name, 0.0)
        return (self.total_tokens / 1_000_000.0) * rate

    def _call_api(self, inputs: list[str]) -> list[list[float]]:
        payload = json.dumps({"model": self.model_name, "input": inputs}).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI Embeddings API HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI Embeddings API connection failed: {exc.reason}") from exc

        usage = body.get("usage") or {}
        self.total_tokens += int(usage.get("total_tokens") or usage.get("prompt_tokens") or 0)
        self.total_requests += 1

        data = sorted(body["data"], key=lambda item: item["index"])
        vectors = [item["embedding"] for item in data]
        for vec in vectors:
            if len(vec) != self.dimensions:
                raise RuntimeError(
                    f"Unexpected embedding dimension {len(vec)}, expected {self.dimensions}"
                )
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = [t.replace("\n", " ").strip() for t in texts[start : start + self.batch_size]]
            vectors.extend(self._call_api(batch))
        return vectors

    def embed_query(self, question: str) -> list[float]:
        cleaned = question.replace("\n", " ").strip()
        if not cleaned:
            raise ValueError("Query text must not be empty")
        return self._call_api([cleaned])[0]
