"""Phase 6 acceptance — the spec's eval corpus:

Leave policy versions:
  v1: 12 days, effective [2024-01-01, 2025-01-01)
  v2: 15 days, effective [2025-01-01, 2026-04-01)
  v3: 20 days, effective [2026-04-01, ∞)

Plus: intent parsing, boundaries, unapproved/future exclusion, ambiguity,
citation validation, insufficient evidence, cross-user isolation, sessions.
"""

import io
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.retrieval.intent import parse_temporal_intent
from tests.test_ingestion import api_user, create_doc

# --- intent unit tests ----------------------------------------------------


def test_intent_current() -> None:
    i = parse_temporal_intent("What is the current leave policy?", today=date(2026, 10, 10))
    assert i.kind == "current" and i.as_of == date(2026, 10, 10)


def test_intent_month_year() -> None:
    i = parse_temporal_intent("What was the allowance in February 2025?")
    assert i.kind == "as_of" and i.as_of == date(2025, 2, 15)


def test_intent_explicit_date() -> None:
    i = parse_temporal_intent("Which policy applied on March 15, 2026?")
    assert i.as_of == date(2026, 3, 15)


def test_intent_iso_date() -> None:
    i = parse_temporal_intent("What applied on 2026-03-31?")
    assert i.as_of == date(2026, 3, 31)


def test_intent_compare_range() -> None:
    i = parse_temporal_intent("What changed between 2024 and 2026?")
    assert i.kind == "compare"
    assert i.compare_a == date(2024, 7, 1) and i.compare_b == date(2026, 7, 1)


def test_intent_bare_year() -> None:
    i = parse_temporal_intent("What was the allowance in 2024?")
    assert i.as_of == date(2024, 7, 1)


def test_intent_past_tense_no_date_is_ambiguous() -> None:
    i = parse_temporal_intent("What was the allowance?")
    assert i.ambiguous is True


# --- helpers ---------------------------------------------------------------


def _upload_and_approve(
    client: TestClient, headers, doc_id: str, content: bytes, frm: str, until: str | None
) -> dict:
    files = {"file": ("policy.txt", io.BytesIO(content))}
    data = {"effective_from": frm}
    if until:
        data["effective_until"] = until
    v = client.post(
        f"/api/v1/documents/{doc_id}/versions", headers=headers, files=files, data=data
    ).json()
    resp = client.post(f"/api/v1/versions/{v['id']}/approve", headers=headers, json={})
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture()
def leave_corpus(client: TestClient) -> tuple[dict, str]:
    """The spec's leave-policy corpus, fully approved."""
    headers = api_user(client, "corp")
    doc_id = create_doc(client, headers, "Employee Leave Policy")
    _upload_and_approve(
        client, headers, doc_id,
        b"The annual leave allowance is 12 days per year.",
        "2024-01-01", "2025-01-01",
    )
    _upload_and_approve(
        client, headers, doc_id,
        b"The annual leave allowance is 15 days per year.",
        "2025-01-01", "2026-04-01",
    )
    _upload_and_approve(
        client, headers, doc_id,
        b"The annual leave allowance is 20 days per year.",
        "2026-04-01", None,
    )
    return headers, doc_id


def ask(client: TestClient, headers, question: str, **kw):
    resp = client.post("/api/v1/chat", headers=headers, json={"question": question, **kw})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_follow_up_pronoun_uses_session_context(
    client: TestClient, leave_corpus
) -> None:
    """'What was it in Feb 2025?' alone carries no topical tokens — the prior
    turn's content must resolve the referent via session context."""
    headers, _ = leave_corpus
    first = ask(client, headers, "What is the current annual leave allowance?")
    assert first["status"] == "answered"
    follow = ask(
        client, headers,
        "What was it in February 2025?",
        session_id=first["session_id"],
    )
    assert follow["status"] == "answered"
    vnums = {c["version_number"] for c in follow["citations"]}
    assert 2 in vnums  # the 15-day version covering Feb 2025


# --- retrieval tests ---------------------------------------------------------


def test_current_question_selects_current_version(client: TestClient, leave_corpus) -> None:
    headers, _ = leave_corpus
    r = ask(client, headers, "What is the current annual leave allowance?")
    assert r["status"] == "answered"
    assert r["intent"]["kind"] == "current"
    cited_versions = {c["version_number"] for c in r["citations"]}
    assert 3 in cited_versions  # today (2026-10) is inside v3's open interval
    assert "20" in r["answer"]


def test_historical_question_selects_historical_version(
    client: TestClient, leave_corpus
) -> None:
    headers, _ = leave_corpus
    r = ask(client, headers, "What was the allowance on February 1, 2025?")
    cited_versions = {c["version_number"] for c in r["citations"]}
    assert 2 in cited_versions
    assert 3 not in cited_versions


def test_boundary_exclusive_end_date(client: TestClient, leave_corpus) -> None:
    """March 31, 2026 → v2; April 1, 2026 → v3 (until is EXCLUSIVE)."""
    headers, _ = leave_corpus
    r1 = ask(client, headers, "What leave allowance applied on 2026-03-31?")
    assert {c["version_number"] for c in r1["citations"]} == {2}
    r2 = ask(client, headers, "What leave allowance applied on 2026-04-01?")
    assert {c["version_number"] for c in r2["citations"]} == {3}


def test_compare_question_gathers_both_periods(
    client: TestClient, leave_corpus
) -> None:
    headers, _ = leave_corpus
    r = ask(client, headers, "What changed in the leave allowance between 2024 and 2026?")
    assert r["intent"]["kind"] == "compare"
    evidence_versions = {e["version_number"] for e in r["evidence"]}
    assert {1, 3} <= evidence_versions  # both periods represented


def test_unapproved_version_not_authoritative(client: TestClient, leave_corpus) -> None:
    headers, doc_id = leave_corpus
    # Upload v4 but leave it pending_review — must not be selected.
    files = {"file": ("policy.txt", io.BytesIO(b"The annual leave allowance is 99 days."))}
    v = client.post(
        f"/api/v1/documents/{doc_id}/versions",
        headers=headers, files=files,
        data={"effective_from": "2026-05-01"},
    ).json()
    r = ask(client, headers, "What is the current annual leave allowance?")
    assert all(c["version_id"] != v["id"] for c in r["citations"])
    assert "20" in r["answer"]


def test_future_effective_version_not_selected_prematurely(
    client: TestClient, leave_corpus
) -> None:
    headers, doc_id = leave_corpus
    files = {"file": ("policy.txt", io.BytesIO(b"The annual leave allowance is 30 days."))}
    v = client.post(
        f"/api/v1/documents/{doc_id}/versions",
        headers=headers, files=files,
        data={"effective_from": "2027-01-01"},
    ).json()
    client.post(f"/api/v1/versions/{v['id']}/approve", headers=headers, json={})
    r = ask(client, headers, "What is the current annual leave allowance?")
    assert all(c["version_id"] != v["id"] for c in r["citations"])
    # But asking about 2027 DOES select it.
    r2 = ask(client, headers, "What will the allowance be in 2027?", as_of_date="2027-06-01")
    # v3 AND v4 both cover 2027 — both may be cited; the new v4 must be there.
    cited_vnums = {c["version_number"] for c in r2["citations"]}
    assert 4 in cited_vnums


def test_overlapping_approved_versions_flag_ambiguity(
    client: TestClient,
) -> None:
    headers = api_user(client, "ovl")
    doc_id = create_doc(client, headers, "Overlap Doc")
    _upload_and_approve(
        client, headers, doc_id, b"Rule says 10 days.", "2024-01-01", "2024-12-31"
    )
    # Second approved version covering the same period — ambiguity, not a silent pick.
    _upload_and_approve(
        client, headers, doc_id, b"Rule says 14 days.", "2024-06-01", "2024-12-31"
    )
    r = ask(client, headers, "What is the rule?", as_of_date="2024-08-01")
    assert any("Multiple approved" in w for w in r["warnings"])
    assert len({c["version_number"] for c in r["citations"] + r["evidence"]}) >= 2


def test_superseded_version_still_answers_historical(
    client: TestClient, leave_corpus, commit_session
) -> None:
    """Superseded ≠ gone: v1 marked superseded must still answer 2024
    questions, and must NOT shadow the approved v3 for current questions."""

    from app.models import DocumentVersion, VersionStatus

    headers, doc_id = leave_corpus
    versions = client.get(f"/api/v1/documents/{doc_id}/versions", headers=headers).json()
    v1 = commit_session.get(DocumentVersion, uuid.UUID(versions[0]["id"]))
    v1.status = VersionStatus.superseded
    commit_session.commit()

    # Historical date → superseded v1 still found.
    r = ask(client, headers, "What was the allowance in 2024?", as_of_date="2024-06-01")
    assert {c["version_number"] for c in r["citations"]} == {1}

    # Current date → approved v3 wins; superseded v1 does not shadow it even
    # though its open interval would otherwise cover nothing past 2025 anyway.
    r2 = ask(client, headers, "What is the current annual leave allowance?")
    assert {c["version_number"] for c in r2["citations"]} == {3}


def test_other_user_gets_no_evidence(client: TestClient, leave_corpus) -> None:
    _headers, _ = leave_corpus
    outsider = api_user(client, "outs")
    r = ask(client, outsider, "What is the current annual leave allowance?")
    assert r["status"] == "insufficient_evidence"
    assert r["citations"] == []


def test_no_matching_evidence_returns_insufficient(
    client: TestClient, leave_corpus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Question about something not in the corpus must not fabricate."""
    from app.core.config import get_settings

    monkeypatch.setenv("RETRIEVAL_SIMILARITY_THRESHOLD", "0.3")
    get_settings.cache_clear()
    try:
        headers, _ = leave_corpus
        r = ask(client, headers, "What is the pizza topping reimbursement policy?")
        assert r["status"] == "insufficient_evidence"
        assert r["citations"] == []
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_citations_reference_real_evidence(client: TestClient, leave_corpus) -> None:
    headers, _ = leave_corpus
    r = ask(client, headers, "What is the current annual leave allowance?")
    evidence_ids = {e["chunk_id"] for e in r["evidence"]}
    for c in r["citations"]:
        assert c["chunk_id"] in evidence_ids
        assert c["effective_from"]
        assert c["page_number"] is None or c["page_number"] >= 1


def test_chat_persists_session_messages_citations(
    client: TestClient, leave_corpus, commit_session
) -> None:
    from sqlalchemy import select

    from app.models import SourceCitation

    headers, _ = leave_corpus
    r = ask(client, headers, "What is the current annual leave allowance?")
    sessions = client.get("/api/v1/chat/sessions", headers=headers).json()
    assert any(s["id"] == r["session_id"] for s in sessions)

    detail = client.get(
        f"/api/v1/chat/sessions/{r['session_id']}", headers=headers
    ).json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant"]

    cited = commit_session.execute(
        select(SourceCitation).where(
            SourceCitation.message_id == __import__("uuid").UUID(r["message_id"])
        )
    ).scalars().all()
    assert len(cited) == len(r["citations"])


def test_other_users_session_is_forbidden(client: TestClient, leave_corpus) -> None:
    headers, _ = leave_corpus
    outsider = api_user(client, "sess-out")
    r = ask(client, headers, "What is the current annual leave allowance?")
    assert (
        client.get(f"/api/v1/chat/sessions/{r['session_id']}", headers=outsider).status_code
        == 403
    )


def test_as_of_date_param_overrides_parsed_intent(
    client: TestClient, leave_corpus
) -> None:
    headers, _ = leave_corpus
    r = ask(
        client, headers,
        "What is the current annual leave allowance?",
        as_of_date="2025-02-01",
    )
    assert r["intent"]["resolved_by"] == "explicit_param"
    assert {c["version_number"] for c in r["citations"]} == {2}
