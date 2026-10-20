import pytest
from fastapi.testclient import TestClient

from app.main import app, cors_origins

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_docs_are_available() -> None:
    response = client.get("/docs")

    assert response.status_code == 200
    assert "Swagger UI" in response.text


def test_cors_configuration_is_an_explicit_origin_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173, https://manager.example.com/,http://localhost:5173",
    )
    assert cors_origins() == [
        "http://localhost:5173",
        "https://manager.example.com",
    ]
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
    with pytest.raises(RuntimeError):
        cors_origins()
