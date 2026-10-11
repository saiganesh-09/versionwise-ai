"""Phase 8 acceptance: the eval harness itself + dashboard/eval endpoints.

Runs the real eval/corpus through the whole pipeline (seed → detect → ask
every case → score). This is the project's regression gate: if temporal
selection ever degrades, these numbers drop.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.eval.evaluator import evaluate, load_corpus
from tests.test_ingestion import api_user

CORPUS_PATH = (
    Path(__file__).resolve().parents[2] / "eval" / "corpus" / "corpus.json"
)


@pytest.fixture(scope="module")
def eval_report(client: TestClient) -> dict:
    headers = api_user(client, "eval")
    corpus = load_corpus(CORPUS_PATH)
    return evaluate(client, headers, corpus)


def test_version_selection_accuracy(eval_report: dict) -> None:
    acc = eval_report["metrics"]["version_selection_accuracy"]
    assert acc is not None and acc >= 0.9, json.dumps(eval_report["cases"], indent=1)


def test_citations_always_valid(eval_report: dict) -> None:
    assert eval_report["metrics"]["citation_validity"] == 1.0


def test_refusal_accuracy(eval_report: dict) -> None:
    assert eval_report["metrics"]["refusal_accuracy"] == 1.0


def test_conflict_flagged(eval_report: dict) -> None:
    assert eval_report["metrics"]["conflict_flag_rate"] == 1.0


def test_status_correct_for_all_cases(eval_report: dict) -> None:
    wrong = [c["case_id"] for c in eval_report["cases"] if not c["status_ok"]]
    assert wrong == []


def test_answer_terms_hit(eval_report: dict) -> None:
    acc = eval_report["metrics"]["answer_terms_accuracy"]
    assert acc is not None and acc >= 0.9


def test_dashboard_stats_scoped(client: TestClient) -> None:
    headers = api_user(client, "dash")
    stats = client.get("/api/v1/dashboard/stats", headers=headers).json()
    for key in (
        "documents", "versions", "chunks", "versions_by_status",
        "ingestion_failures", "open_conflicts", "my_chat_sessions",
    ):
        assert key in stats
    assert stats["documents"] >= 0


def test_eval_latest_endpoint(client: TestClient) -> None:
    headers = api_user(client, "evl")
    resp = client.get("/api/v1/eval/latest", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    # Either a real report (run_eval.py has run) or the honest placeholder.
    assert "status" in body or "metrics" in body


def test_dashboard_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/dashboard/stats").status_code == 401
    assert client.get("/api/v1/eval/latest").status_code == 401
