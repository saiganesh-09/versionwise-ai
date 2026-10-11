"""Phase 7 acceptance: contradiction detection, classification, review
workflow, dedupe, version comparison, and chat conflict warnings."""


from fastapi.testclient import TestClient

from tests.test_ingestion import api_user, create_doc
from tests.test_retrieval import _upload_and_approve, ask


def _doc_with_version(client, headers, title, text, frm="2024-01-01", until=None):
    doc_id = create_doc(client, headers, title)
    v = _upload_and_approve(client, headers, doc_id, text, frm, until)
    return doc_id, v


def test_cross_document_contradiction_detected(client: TestClient) -> None:
    """Leave policy says 12 days; handbook says 10 — same period, different
    docs → contradictory finding."""
    headers = api_user(client, "cf")
    _doc_with_version(
        client, headers, "Leave Policy",
        b"Employees receive 12 days of annual leave.",
    )
    _doc_with_version(
        client, headers, "Manager Handbook",
        b"Employees receive 10 days of annual leave.",
    )
    resp = client.post("/api/v1/conflicts/detect", headers=headers, json={})
    assert resp.status_code == 200, resp.text
    findings = resp.json()["findings"]
    contradictions = [f for f in findings if f["conflict_type"] == "contradictory"]
    assert len(contradictions) >= 1
    c = contradictions[0]
    assert c["status"] == "potential"
    assert "12" in c["evidence_a"] + c["evidence_b"]
    assert "10" in c["evidence_a"] + c["evidence_b"]


def test_same_doc_newer_version_is_update_not_contradiction(
    client: TestClient,
) -> None:
    """v1 says 12, v2 says 15 for a LATER interval → updated_by_newer_version,
    not contradictory."""
    headers = api_user(client, "upd")
    doc_id = create_doc(client, headers, "Policy")
    _upload_and_approve(
        client, headers, doc_id, b"Allowance is 12 days.", "2024-01-01", "2025-01-01"
    )
    _upload_and_approve(
        client, headers, doc_id, b"Allowance is 15 days.", "2025-01-01", None
    )
    resp = client.post("/api/v1/conflicts/detect", headers=headers, json={})
    types = {f["conflict_type"] for f in resp.json()["findings"]}
    assert "contradictory" not in types
    assert "updated_by_newer_version" in types


def test_identical_passages_no_finding(client: TestClient) -> None:
    headers = api_user(client, "same")
    _doc_with_version(
        client, headers, "A", b"Employees receive 12 days of annual leave."
    )
    _doc_with_version(
        client, headers, "B", b"Employees receive 12 days of annual leave."
    )
    resp = client.post("/api/v1/conflicts/detect", headers=headers, json={})
    assert all(
        f["conflict_type"] != "contradictory" for f in resp.json()["findings"]
    )


def test_detection_dedupes_on_rerun(client: TestClient) -> None:
    headers = api_user(client, "dd")
    _doc_with_version(client, headers, "P", b"Allowance is 12 days.")
    _doc_with_version(client, headers, "H", b"Allowance is 10 days.")
    first = client.post("/api/v1/conflicts/detect", headers=headers, json={}).json()
    second = client.post("/api/v1/conflicts/detect", headers=headers, json={}).json()
    first_ids = {f["id"] for f in first["findings"]}
    second_ids = {f["id"] for f in second["findings"]}
    assert first_ids == second_ids  # same rows refreshed, not duplicated


def test_review_workflow(client: TestClient) -> None:
    headers = api_user(client, "rev")
    _doc_with_version(client, headers, "P", b"Allowance is 12 days.")
    _doc_with_version(client, headers, "H", b"Allowance is 10 days.")
    finding = client.post(
        "/api/v1/conflicts/detect", headers=headers, json={}
    ).json()["findings"][0]

    confirm = client.post(
        f"/api/v1/conflicts/{finding['id']}/review",
        headers=headers,
        json={"action": "confirm", "note": "Real contradiction — legal to resolve"},
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"
    assert confirm.json()["reviewed_by"] is not None
    assert confirm.json()["resolution_note"] == "Real contradiction — legal to resolve"

    resolve = client.post(
        f"/api/v1/conflicts/{finding['id']}/review",
        headers=headers,
        json={"action": "resolve", "note": "Handbook corrected in v2"},
    )
    assert resolve.json()["status"] == "resolved"


def test_dismissed_finding_not_reopened(client: TestClient) -> None:
    headers = api_user(client, "dis")
    _doc_with_version(client, headers, "P", b"Allowance is 12 days.")
    _doc_with_version(client, headers, "H", b"Allowance is 10 days.")
    finding = client.post(
        "/api/v1/conflicts/detect", headers=headers, json={}
    ).json()["findings"][0]
    client.post(
        f"/api/v1/conflicts/{finding['id']}/review",
        headers=headers, json={"action": "dismiss", "note": "Different employee classes"},
    )
    # Re-run detection — the finding must NOT flip back to potential.
    second = client.post(
        "/api/v1/conflicts/detect", headers=headers, json={}
    ).json()["findings"]
    kept = [f for f in second if f["id"] == finding["id"]]
    assert kept[0]["status"] == "dismissed"


def test_conflicts_filtered_by_status(client: TestClient) -> None:
    headers = api_user(client, "flt")
    _doc_with_version(client, headers, "P", b"Allowance is 12 days.")
    _doc_with_version(client, headers, "H", b"Allowance is 10 days.")
    client.post("/api/v1/conflicts/detect", headers=headers, json={})
    listed = client.get(
        "/api/v1/conflicts?status=potential", headers=headers
    ).json()
    assert all(c["status"] == "potential" for c in listed)
    assert len(listed) >= 1


def test_outsider_cannot_see_conflicts(client: TestClient) -> None:
    headers = api_user(client, "sec1")
    _doc_with_version(client, headers, "P", b"Allowance is 12 days.")
    _doc_with_version(client, headers, "H", b"Allowance is 10 days.")
    client.post("/api/v1/conflicts/detect", headers=headers, json={})
    outsider = api_user(client, "sec2")
    assert client.get("/api/v1/conflicts", headers=outsider).json() == []


def test_chat_warns_about_conflicting_evidence(client: TestClient) -> None:
    headers = api_user(client, "warn")
    _doc_with_version(
        client, headers, "Leave Policy", b"Annual leave is 12 days."
    )
    _doc_with_version(
        client, headers, "Handbook", b"Annual leave is 10 days."
    )
    client.post("/api/v1/conflicts/detect", headers=headers, json={})
    r = ask(client, headers, "What is the annual leave allowance?")
    assert any("conflict" in w.lower() for w in r["warnings"])


def test_compare_versions_diff(client: TestClient) -> None:
    headers = api_user(client, "cmp")
    doc_id = create_doc(client, headers, "Policy")
    v1 = _upload_and_approve(
        client, headers, doc_id, b"Allowance is 12 days.", "2024-01-01", "2025-01-01"
    )
    v2 = _upload_and_approve(
        client, headers, doc_id, b"Allowance is 15 days.", "2025-01-01", None
    )
    resp = client.get(
        f"/api/v1/compare?version_a_id={v1['id']}&version_b_id={v2['id']}",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["changed_hint"] is True
    assert any("12" in r for r in body["removed"])
    assert any("15" in a for a in body["added"])
    assert body["version_a"]["version_number"] == 1
    assert body["version_b"]["version_number"] == 2


def test_compare_cross_document_rejected(client: TestClient) -> None:
    headers = api_user(client, "xcmp")
    _, va = _doc_with_version(client, headers, "A", b"alpha text")
    _, vb = _doc_with_version(client, headers, "B", b"beta text")
    resp = client.get(
        f"/api/v1/compare?version_a_id={va['id']}&version_b_id={vb['id']}",
        headers=headers,
    )
    assert resp.status_code == 400


def test_conflicts_endpoints_require_auth(client: TestClient) -> None:
    import uuid as _u

    assert client.get("/api/v1/conflicts").status_code == 401
    assert client.post("/api/v1/conflicts/detect", json={}).status_code == 401
    assert client.post(
        f"/api/v1/conflicts/{_u.uuid4()}/review", json={"action": "confirm"}
    ).status_code == 401
