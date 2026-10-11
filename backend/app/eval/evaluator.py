"""Evaluation harness — seeds a corpus and scores the retrieval engine.

Lives in the app package (not scripts/) so the test-suite exercises the exact
same path as `scripts/run_eval.py`.

Metrics reported:
- version_selection_accuracy: expected version numbers all present in evidence
- citation_validity: cited chunks ⊆ retrieved evidence (must be 1.0 — the
  validator drops anything else, this is the regression alarm)
- refusal_accuracy: insufficient_evidence returned exactly where expected
- conflict_flag_rate: conflict warnings surfaced where expected
"""

import io
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CaseResult:
    case_id: str
    question: str
    status: str
    expected_status: str
    status_ok: bool
    expected_versions: list[int]
    evidence_versions: list[int]
    version_hit: bool | None      # None when not applicable
    answer_terms_ok: bool | None
    citations_valid: bool
    conflict_warning_ok: bool | None
    answer: str = ""
    warnings: list[str] = field(default_factory=list)


def load_corpus(corpus_path: str | Path) -> dict[str, Any]:
    p = Path(corpus_path)
    corpus = json.loads(p.read_text(encoding="utf-8"))
    corpus["_base"] = p.parent
    return corpus


def seed_corpus(client, headers: dict[str, str], corpus: dict[str, Any]) -> dict:
    """Upload + approve every version in the corpus. Returns title → doc_id."""
    base = corpus["_base"] / "files"
    doc_ids: dict[str, str] = {}
    for doc in corpus["documents"]:
        resp = client.post(
            "/api/v1/documents",
            headers=headers,
            json={"title": doc["title"], "document_type": doc.get("document_type", "policy")},
        )
        assert resp.status_code == 201, resp.text
        doc_id = resp.json()["id"]
        doc_ids[doc["title"]] = doc_id
        for v in doc["versions"]:
            data = (base / v["file"]).read_bytes()
            form = {"effective_from": v["effective_from"]}
            if v.get("effective_until"):
                form["effective_until"] = v["effective_until"]
            up = client.post(
                f"/api/v1/documents/{doc_id}/versions",
                headers=headers,
                files={"file": (v["file"], io.BytesIO(data))},
                data=form,
            )
            assert up.status_code == 201, up.text
            ap = client.post(
                f"/api/v1/versions/{up.json()['id']}/approve", headers=headers, json={}
            )
            assert ap.status_code == 200, ap.text
    return doc_ids


def run_case(client, headers: dict[str, str], case: dict) -> dict:
    return client.post(
        "/api/v1/chat", headers=headers, json={"question": case["question"]}
    ).json()


def score_case(case: dict, response: dict) -> CaseResult:
    exp = case["expect"]
    expected_status = exp["status"]
    status_ok = response["status"] == expected_status

    evidence_versions = sorted({e["version_number"] for e in response["evidence"]})
    evidence_pairs = {
        (e["document_title"], e["version_number"]) for e in response["evidence"]
    }
    cited_ids = {c["chunk_id"] for c in response["citations"]}
    evidence_ids = {e["chunk_id"] for e in response["evidence"]}
    citations_valid = cited_ids <= evidence_ids

    version_hit = None
    if "version_numbers" in exp:
        # (document title, version_number) pairs — version numbers collide
        # across documents, so number-only matching is meaningless.
        exp_pairs = {(exp["document"], v) for v in exp["version_numbers"]}
        version_hit = exp_pairs <= evidence_pairs
    elif "evidence_versions" in exp:
        exp_pairs = {(exp["document"], v) for v in exp["evidence_versions"]}
        version_hit = exp_pairs <= evidence_pairs

    terms_ok = None
    if "answer_terms" in exp:
        answer_l = response["answer"].lower()
        terms_ok = all(t.lower() in answer_l for t in exp["answer_terms"])

    conflict_ok = None
    if exp.get("conflict_warning_expected"):
        conflict_ok = any("conflict" in w.lower() for w in response["warnings"])

    return CaseResult(
        case_id=case["id"],
        question=case["question"],
        status=response["status"],
        expected_status=expected_status,
        status_ok=status_ok,
        expected_versions=exp.get("version_numbers") or exp.get("evidence_versions") or [],
        evidence_versions=evidence_versions,
        version_hit=version_hit,
        answer_terms_ok=terms_ok,
        citations_valid=citations_valid,
        conflict_warning_ok=conflict_ok,
        answer=response["answer"][:400],
        warnings=response["warnings"],
    )


def evaluate(client, headers: dict[str, str], corpus: dict[str, Any]) -> dict:
    """Seed + detect conflicts + run all cases; returns a serializable report."""
    seed_corpus(client, headers, corpus)
    client.post("/api/v1/conflicts/detect", headers=headers, json={})

    results = [score_case(c, run_case(client, headers, c)) for c in corpus["cases"]]

    answered = [r for r in results if r.version_hit is not None]
    terms_cases = [r for r in results if r.answer_terms_ok is not None]
    refusals_expected = [r for r in results if r.expected_status == "insufficient_evidence"]
    conflict_expected = [r for r in results if r.conflict_warning_ok is not None]

    metrics = {
        "version_selection_accuracy": (
            sum(1 for r in answered if r.version_hit) / len(answered)
            if answered else None
        ),
        "answer_terms_accuracy": (
            sum(1 for r in terms_cases if r.answer_terms_ok) / len(terms_cases)
            if terms_cases else None
        ),
        "citation_validity": (
            sum(1 for r in results if r.citations_valid) / len(results)
            if results else None
        ),
        "refusal_accuracy": (
            sum(1 for r in refusals_expected if r.status_ok) / len(refusals_expected)
            if refusals_expected else None
        ),
        "conflict_flag_rate": (
            sum(1 for r in conflict_expected if r.conflict_warning_ok)
            / len(conflict_expected)
            if conflict_expected else None
        ),
    }
    return {
        "corpus": corpus["name"],
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "totals": {
            "cases": len(results),
            "status_correct": sum(1 for r in results if r.status_ok),
        },
        "metrics": metrics,
        "cases": [r.__dict__ for r in results],
    }
