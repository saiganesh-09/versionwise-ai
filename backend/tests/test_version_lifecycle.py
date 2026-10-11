"""Phase 5 acceptance: approve/reject/supersede lifecycle, permission rules,
and preservation of history."""

import io
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, User
from tests.test_ingestion import api_user, create_doc


def _upload(
    client, headers, doc_id, content: bytes, frm="2024-01-01", until=None,
    filename: str = "v.txt",
):
    files = {"file": (filename, io.BytesIO(content))}
    data = {"effective_from": frm}
    if until:
        data["effective_until"] = until
    resp = client.post(
        f"/api/v1/documents/{doc_id}/versions", headers=headers, files=files, data=data
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_approve_happy_path(client: TestClient) -> None:
    headers = api_user(client, "app")
    doc_id = create_doc(client, headers)
    v = _upload(client, headers, doc_id, b"policy text v1")
    assert v["status"] == "pending_review"

    resp = client.post(f"/api/v1/versions/{v['id']}/approve", headers=headers, json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "approved"
    assert body["approved_by"] is not None
    assert body["approved_at"] is not None


def test_approve_twice_rejected(client: TestClient) -> None:
    headers = api_user(client, "app2")
    doc_id = create_doc(client, headers)
    v = _upload(client, headers, doc_id, b"policy text")
    client.post(f"/api/v1/versions/{v['id']}/approve", headers=headers, json={})
    again = client.post(f"/api/v1/versions/{v['id']}/approve", headers=headers, json={})
    assert again.status_code == 409


def test_approve_requires_completed_ingestion(client: TestClient) -> None:
    headers = api_user(client, "bad-ing")
    doc_id = create_doc(client, headers)
    # Scanned PDF → ingestion fails, so approval must refuse.
    from tests.test_ingestion import make_scanned_pdf

    v = _upload(client, headers, doc_id, make_scanned_pdf(), filename="scan.pdf")
    assert v["ingestion_status"] == "failed"
    resp = client.post(f"/api/v1/versions/{v['id']}/approve", headers=headers, json={})
    assert resp.status_code == 409
    assert "ingestion" in resp.json()["error"]["message"].lower()


def test_reject_archives_version(client: TestClient) -> None:
    headers = api_user(client, "rej")
    doc_id = create_doc(client, headers)
    v = _upload(client, headers, doc_id, b"policy text")
    resp = client.post(
        f"/api/v1/versions/{v['id']}/reject",
        headers=headers,
        json={"reason": "Content needs legal review"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "archived"
    assert body["extra"]["rejection_reason"] == "Content needs legal review"


def test_supersede_on_approve(client: TestClient) -> None:
    headers = api_user(client, "sup")
    doc_id = create_doc(client, headers)
    v1 = _upload(client, headers, doc_id, b"old policy", "2024-01-01", "2024-12-31")
    v2 = _upload(client, headers, doc_id, b"new policy", "2025-01-01")
    client.post(f"/api/v1/versions/{v1['id']}/approve", headers=headers, json={})

    resp = client.post(
        f"/api/v1/versions/{v2['id']}/approve",
        headers=headers,
        json={"supersede_version_id": v1["id"]},
    )
    assert resp.status_code == 200
    assert resp.json()["supersedes_version_id"] == v1["id"]

    v1_after = client.get(f"/api/v1/versions/{v1['id']}", headers=headers).json()
    assert v1_after["status"] == "superseded"
    # History preserved: chunks of the superseded version still retrievable.
    chunks = client.get(
        f"/api/v1/versions/{v1['id']}/chunks", headers=headers
    ).json()
    assert len(chunks) > 0


def test_supersede_requires_approved_target(client: TestClient) -> None:
    headers = api_user(client, "sup2")
    doc_id = create_doc(client, headers)
    v1 = _upload(client, headers, doc_id, b"v1")
    v2 = _upload(client, headers, doc_id, b"v2")
    # v1 still pending_review → cannot be superseded.
    resp = client.post(
        f"/api/v1/versions/{v2['id']}/approve",
        headers=headers,
        json={"supersede_version_id": v1["id"]},
    )
    assert resp.status_code == 409


def test_supersede_cross_document_rejected(client: TestClient) -> None:
    headers = api_user(client, "xs")
    doc_a = create_doc(client, headers, "Doc A")
    doc_b = create_doc(client, headers, "Doc B")
    va = _upload(client, headers, doc_a, b"doc a v1")
    vb = _upload(client, headers, doc_b, b"doc b v1")
    client.post(f"/api/v1/versions/{va['id']}/approve", headers=headers, json={})
    resp = client.post(
        f"/api/v1/versions/{vb['id']}/approve",
        headers=headers,
        json={"supersede_version_id": va["id"]},  # different document!
    )
    assert resp.status_code == 404


def test_approve_requires_manage_access(
    client: TestClient, commit_session: Session
) -> None:
    owner_h = api_user(client, "mgr-o")
    reader_h = api_user(client, "mgr-r")
    doc_id = create_doc(client, owner_h)
    v = _upload(client, owner_h, doc_id, b"policy")
    # Read grant — can view but must NOT be able to approve.
    from sqlalchemy import select as _sel

    from app.models import DocumentPermission, DocumentPermissionGrant

    reader = commit_session.execute(
        _sel(User).where(User.email.like("mgr-r%"))
    ).scalar_one()
    commit_session.add(
        DocumentPermissionGrant(
            document_id=uuid.UUID(doc_id),
            user_id=reader.id,
            permission=DocumentPermission.read,
        )
    )
    commit_session.commit()

    # Visible (200) but approve forbidden (403)
    assert client.get(f"/api/v1/versions/{v['id']}", headers=reader_h).status_code == 200
    resp = client.post(
        f"/api/v1/versions/{v['id']}/approve", headers=reader_h, json={}
    )
    assert resp.status_code == 403


def test_approve_writes_audit_log(client: TestClient, commit_session: Session) -> None:
    headers = api_user(client, "aud")
    doc_id = create_doc(client, headers)
    v = _upload(client, headers, doc_id, b"policy")
    client.post(f"/api/v1/versions/{v['id']}/approve", headers=headers, json={})
    actions = commit_session.execute(
        select(AuditLog.action).where(
            AuditLog.target_id == uuid.UUID(v["id"])
        )
    ).scalars().all()
    assert "version.approved" in actions


def test_approval_endpoints_require_auth(client: TestClient) -> None:
    fake = str(uuid.uuid4())
    assert client.post(f"/api/v1/versions/{fake}/approve", json={}).status_code == 401
    assert client.post(f"/api/v1/versions/{fake}/reject", json={}).status_code == 401


def test_historical_version_list_shows_full_lineage(client: TestClient) -> None:
    headers = api_user(client, "hist")
    doc_id = create_doc(client, headers)
    v1 = _upload(client, headers, doc_id, b"v1", "2024-01-01", "2024-12-31")
    v2 = _upload(client, headers, doc_id, b"v2", "2025-01-01")
    client.post(f"/api/v1/versions/{v1['id']}/approve", headers=headers, json={})
    client.post(
        f"/api/v1/versions/{v2['id']}/approve",
        headers=headers,
        json={"supersede_version_id": v1["id"]},
    )
    versions = client.get(
        f"/api/v1/documents/{doc_id}/versions", headers=headers
    ).json()
    by_num = {v["version_number"]: v for v in versions}
    assert by_num[1]["status"] == "superseded"
    assert by_num[2]["status"] == "approved"
    assert by_num[2]["supersedes_version_id"] == v1["id"]
