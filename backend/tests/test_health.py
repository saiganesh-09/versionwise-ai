from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "VersionWise AI"
    assert "version" in body


def test_readiness_reports_database_check(client: TestClient) -> None:
    """Readiness must always report a database check, whatever its state."""
    resp = client.get("/api/v1/health/ready")
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert body["status"] in ("ready", "degraded")
    checks = {c["name"]: c for c in body["checks"]}
    assert "database" in checks
    assert checks["database"]["status"] in ("ok", "unavailable")


def test_unknown_route_returns_404(client: TestClient) -> None:
    resp = client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
