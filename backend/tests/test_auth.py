"""Phase 3 acceptance: auth flows, token rules, permission enforcement."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    DocumentPermission,
    DocumentPermissionGrant,
    User,
    UserRole,
)

PASSWORD = "Sup3rSecret!"


def register(client: TestClient, email: str, name: str = "T User") -> dict:
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": name, "password": PASSWORD},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def login(client: TestClient, email: str, password: str = PASSWORD) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_api_user(
    client: TestClient, prefix: str, role: UserRole = UserRole.user
) -> tuple[dict, dict[str, str]]:
    """Register via API (always 'user' role) then, if a higher role is needed,
    bump it directly in the DB — mirroring an admin doing it, not the API."""
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"
    body = register(client, email)
    return body, auth_headers(login(client, email))


def test_register_login_me_flow(client: TestClient) -> None:
    user, headers = make_api_user(client, "flow")
    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == user["email"]
    assert resp.json()["role"] == "user"


def test_register_duplicate_email_409(client: TestClient) -> None:
    email = f"dupe-{uuid.uuid4().hex[:8]}@example.com"
    register(client, email)
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "X", "password": PASSWORD},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


def test_login_wrong_password_401(client: TestClient) -> None:
    email = f"wp-{uuid.uuid4().hex[:8]}@example.com"
    register(client, email)
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "wrong-password"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


def test_register_cannot_escalate_role(client: TestClient) -> None:
    email = f"esc-{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Sneaky",
            "password": PASSWORD,
            "role": "admin",  # must be ignored, not honored
        },
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "user"


def test_me_requires_token(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401


def test_bad_token_rejected(client: TestClient) -> None:
    resp = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not.a.real.token"}
    )
    assert resp.status_code == 401


def test_documents_list_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/documents").status_code == 401


def test_logout(client: TestClient) -> None:
    _, headers = make_api_user(client, "lo")
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204


def test_cross_user_document_is_hidden(client: TestClient) -> None:
    """User B cannot list or fetch user A's document."""
    _, headers_a = make_api_user(client, "alice")
    _, headers_b = make_api_user(client, "bob")

    resp = client.post(
        "/api/v1/documents",
        headers=headers_a,
        json={"title": "Alice Private Policy", "document_type": "policy"},
    )
    assert resp.status_code == 201
    doc_id = resp.json()["id"]

    listed = client.get("/api/v1/documents", headers=headers_b).json()
    assert all(d["id"] != doc_id for d in listed)

    detail = client.get(f"/api/v1/documents/{doc_id}", headers=headers_b)
    assert detail.status_code == 404  # not 403 — don't leak existence


def test_explicit_read_grant_allows_access(
    client: TestClient, commit_session: Session
) -> None:
    user_a, headers_a = make_api_user(client, "ga")
    user_b, headers_b = make_api_user(client, "gb")
    doc_id = client.post(
        "/api/v1/documents", headers=headers_a, json={"title": "Shared Doc"}
    ).json()["id"]

    grant = DocumentPermissionGrant(
        document_id=uuid.UUID(doc_id),
        user_id=uuid.UUID(user_b["id"]),
        permission=DocumentPermission.read,
        granted_by=uuid.UUID(user_a["id"]),
    )
    commit_session.add(grant)
    commit_session.commit()

    detail = client.get(f"/api/v1/documents/{doc_id}", headers=headers_b)
    assert detail.status_code == 200
    assert detail.json()["title"] == "Shared Doc"


def test_admin_sees_all_documents(
    client: TestClient, commit_session: Session
) -> None:
    _, headers_a = make_api_user(client, "own")
    doc_id = client.post(
        "/api/v1/documents", headers=headers_a, json={"title": "Hidden From Others"}
    ).json()["id"]

    admin_email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    commit_session.add(
        User(
            email=admin_email,
            full_name="Admin",
            password_hash=hash_password(PASSWORD),
            role=UserRole.admin,
        )
    )
    commit_session.commit()
    admin_headers = auth_headers(login(client, admin_email))

    detail = client.get(f"/api/v1/documents/{doc_id}", headers=admin_headers)
    assert detail.status_code == 200


def test_inactive_user_token_rejected(
    client: TestClient, commit_session: Session
) -> None:
    user, headers = make_api_user(client, "dead")
    # Deactivate the account after the token was issued — tokens must not
    # outlive account status.
    row = commit_session.get(User, uuid.UUID(user["id"]))
    row.is_active = False
    commit_session.commit()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_error_shape_consistent(client: TestClient) -> None:
    resp = client.get("/api/v1/auth/me")
    body = resp.json()
    assert set(body["error"].keys()) == {"code", "message", "details"}


def test_malformed_uuid_422(client: TestClient) -> None:
    _, headers = make_api_user(client, "uuid")
    resp = client.get("/api/v1/documents/not-a-uuid", headers=headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_document_share_grant_and_revoke(client: TestClient) -> None:
    owner_email = f"share-owner-{uuid.uuid4().hex[:8]}@example.com"
    other_email = f"share-other-{uuid.uuid4().hex[:8]}@example.com"
    register(client, owner_email)
    register(client, other_email)
    owner = auth_headers(login(client, owner_email))
    other = auth_headers(login(client, other_email))
    resp = client.post(
        "/api/v1/documents", headers=owner,
        json={"title": "Shared Policy", "document_type": "policy"},
    )
    doc_id = resp.json()["id"]

    # Other user can't see it yet
    assert client.get(
        f"/api/v1/documents/{doc_id}", headers=other
    ).status_code == 404

    # Grant read access
    r = client.post(
        f"/api/v1/documents/{doc_id}/permissions", headers=owner,
        json={"email": other_email, "permission": "read"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["permission"] == "read"

    # Now visible
    assert client.get(
        f"/api/v1/documents/{doc_id}", headers=other
    ).status_code == 200
    assert any(
        d["id"] == doc_id
        for d in client.get("/api/v1/documents", headers=other).json()
    )

    # List grants (grantee can't — read only)
    grants = client.get(
        f"/api/v1/documents/{doc_id}/permissions", headers=owner
    ).json()
    assert len(grants) == 1
    assert client.get(
        f"/api/v1/documents/{doc_id}/permissions", headers=other
    ).status_code == 403

    # Revoke → hidden again
    uid = grants[0]["user_id"]
    assert client.delete(
        f"/api/v1/documents/{doc_id}/permissions/{uid}", headers=owner
    ).status_code == 204
    assert client.get(
        f"/api/v1/documents/{doc_id}", headers=other
    ).status_code == 404

    # Edge cases
    assert client.post(
        f"/api/v1/documents/{doc_id}/permissions", headers=owner,
        json={"email": "ghost@example.com", "permission": "read"},
    ).status_code == 404
