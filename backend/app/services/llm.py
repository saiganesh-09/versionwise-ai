"""LLM provider adapters.

`openai` / `openai_compatible` → POST {base}/chat/completions with JSON-mode.
`mock` → deterministic extractive answer built from the actual evidence —
citations always point at real chunks, so the grounded pipeline is fully
verifiable without credentials.
"""

import json
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings


class LLMError(Exception):
    pass


class LLMProvider(Protocol):
    def complete(self, system: str, user: str) -> str: ...


class OpenAILLM:
    def __init__(self, settings: Settings) -> None:
        if not settings.llm_api_key:
            raise LLMError(
                f"LLM_API_KEY is required for provider {settings.llm_provider!r}."
            )
        self._model = settings.llm_model
        self._client = httpx.Client(
            base_url=(settings.llm_base_url or "https://api.openai.com/v1").rstrip("/"),
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            timeout=settings.llm_timeout_seconds,
        )

    def complete(self, system: str, user: str) -> str:
        resp = self._client.post(
            "/chat/completions",
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
            },
        )
        if resp.status_code != 200:
            raise LLMError(f"LLM request failed: HTTP {resp.status_code}")
        return resp.json()["choices"][0]["message"]["content"]


class MockLLM:
    """Extractive stand-in: quotes the top evidence passage and emits the same
    JSON contract as real providers. Only cites chunks it was actually shown."""

    def complete(self, system: str, user: str) -> str:
        payload = json.loads(user)
        evidence = payload.get("evidence", [])
        question = payload.get("question", "")
        if not evidence:
            return json.dumps(
                {
                    "answer": "I don't have enough evidence in the indexed "
                    "document versions to answer that.",
                    "citations": [],
                    "warnings": ["no_evidence"],
                }
            )
        top = evidence[0]
        interval = (
            f"effective {top['effective_from']}"
            + (f" - {top['effective_until']}" if top["effective_until"] else " - present")
        )
        snippet = top["content"][:280].strip()
        answer = (
            f"According to '{top['document_title']}' (version "
            f"{top['version_number']}, {interval}): {snippet}"
        )
        return json.dumps(
            {
                "answer": answer,
                "citations": [top["chunk_id"]],
                "warnings": [],
                "question_echo": question[:80],
            }
        )


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    if settings.llm_provider == "mock":
        return MockLLM()
    return OpenAILLM(settings)
