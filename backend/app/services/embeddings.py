"""Embedding provider adapters.

`openai` / `openai_compatible` → POST {base}/embeddings (OpenAI API shape,
works with OpenAI and compatible providers via EMBEDDING_BASE_URL).
`mock` → deterministic hash-seeded vectors for dev/tests without credentials.

Retrieval code only ever sees `EmbeddingProvider.embed()` — swapping
providers is an env change, not a code change.
"""

import hashlib
import random
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings


class EmbeddingError(Exception):
    pass


class EmbeddingProvider(Protocol):
    @property
    def dimensions(self) -> int: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbeddings:
    def __init__(self, settings: Settings) -> None:
        if not settings.embedding_api_key:
            raise EmbeddingError(
                "EMBEDDING_API_KEY is required for provider "
                f"{settings.embedding_provider!r}."
            )
        self._model = settings.embedding_model
        self._dims = settings.embedding_dimensions
        self._timeout = settings.embedding_timeout_seconds
        self._client = httpx.Client(
            base_url=(settings.embedding_base_url or "https://api.openai.com/v1").rstrip("/"),
            headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
            timeout=self._timeout,
        )

    @property
    def dimensions(self) -> int:
        return self._dims

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = self._client.post(
            "/embeddings", json={"model": self._model, "input": texts}
        )
        if resp.status_code != 200:
            raise EmbeddingError(f"Embedding request failed: HTTP {resp.status_code}")
        data = resp.json()["data"]
        vectors = [row["embedding"] for row in sorted(data, key=lambda r: r["index"])]
        if len(vectors) != len(texts):
            raise EmbeddingError("Embedding count mismatch from provider")
        return vectors


class MockEmbeddings:
    """Deterministic vectors from content hashes — same text → same vector,
    similar texts land nowhere near each other (fine for pipeline tests,
    not for similarity assertions)."""

    def __init__(self, dimensions: int) -> None:
        self._dims = dimensions

    @property
    def dimensions(self) -> int:
        return self._dims

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            seed = int.from_bytes(hashlib.sha256(t.encode()).digest()[:8], "big")
            rng = random.Random(seed)
            v = [rng.gauss(0, 1) for _ in range(self._dims)]
            norm = sum(x * x for x in v) ** 0.5 or 1.0
            out.append([x / norm for x in v])
        return out


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    settings = settings or get_settings()
    if settings.embedding_provider == "mock":
        return MockEmbeddings(settings.embedding_dimensions)
    return OpenAIEmbeddings(settings)
