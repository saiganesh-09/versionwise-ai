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
        if payload.get("task") == "conflict_check":
            return self._conflict_check(payload)
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
        # Quote up to the top-3 passages — closer to how a real model uses
        # the whole evidence set than a single-snippet echo.
        parts: list[str] = []
        cited: list[str] = []
        for e in evidence[:3]:
            interval = (
                f"effective {e['effective_from']}"
                + (f" - {e['effective_until']}" if e["effective_until"] else " - present")
            )
            parts.append(
                f"'{e['document_title']}' (v{e['version_number']}, {interval})"
                f" states: {e['content'][:220].strip()}"
            )
            cited.append(e["chunk_id"])
        answer = "Based on the retrieved evidence — " + " | ".join(parts)
        return json.dumps(
            {
                "answer": answer,
                "citations": cited,
                "warnings": [],
                "question_echo": question[:80],
            }
        )

    @staticmethod
    def _conflict_check(payload: dict) -> str:
        """Deterministic verdict mirroring the real classifier's contract."""
        import re

        nums = re.compile(r"\d+(?:\.\d+)?")
        a, b = payload["evidence_a"], payload["evidence_b"]
        na, nb = set(nums.findall(a)), set(nums.findall(b))
        if a.strip().lower() == b.strip().lower() or na == nb:
            verdict, conf, why = "consistent", 0.7, "No differing assertions."
        elif payload.get("same_document") and not payload.get("intervals_overlap"):
            verdict, conf, why = (
                "updated_by_newer_version", 0.9,
                "Newer version changes the value for a later period.",
            )
        elif payload.get("intervals_overlap"):
            verdict, conf, why = (
                "contradictory", 0.85,
                f"Overlapping periods assert different values ({sorted(na)} vs {sorted(nb)}).",
            )
        else:
            verdict, conf, why = "context_dependent", 0.4, "Differences without overlap."
        return json.dumps(
            {"verdict": verdict, "confidence": conf, "explanation": why}
        )


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    if settings.llm_provider == "mock":
        return MockLLM()
    return OpenAILLM(settings)
