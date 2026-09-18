from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_and_metrics_are_exposed():
    live = client.get("/health/live")
    assert live.status_code == 200
    assert live.json() == {"status": "ok"}
    assert live.headers["x-request-id"]

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "nba_http_requests_total" in metrics.text


def test_v1_and_legacy_model_routes_are_compatible(monkeypatch):
    bundle = {
        "meta": {"model_version": 3, "n_shots": 10, "seasons": ["2025-26"]},
        "feature_columns": ["distance"], "delta_distribution": [],
    }
    monkeypatch.setattr("app.routers.ml.ml.load_model", lambda: bundle)
    current = client.get("/api/v1/ml/model-info")
    legacy = client.get("/api/ml/model-info")
    assert current.status_code == legacy.status_code == 200
    assert current.json() == legacy.json()
    assert current.headers["x-api-version"] == "v1"
    assert "x-data-cache" in current.headers


def test_invalid_route_parameters_return_problem_details():
    response = client.get("/api/v1/games/not-a-game/investigate")
    assert response.status_code == 422
    body = response.json()
    assert body["type"] == "urn:nba-stat-analyzer:validation"
    assert body["request_id"]
    assert body["retryable"] is False

    bad_season = client.get("/api/v1/players/1/summary?season=2025")
    assert bad_season.status_code == 422

    impossible_season = client.get("/api/v1/players/1/summary?season=2025-99")
    assert impossible_season.status_code == 422
    blank_search = client.get("/api/v1/players/search?q=%20%20")
    assert blank_search.status_code == 422


def test_date_range_validation_is_safe():
    response = client.get(
        "/api/v1/players/1/overview?date_from=2025-10-10&date_to=2025-10-01"
    )
    assert response.status_code == 422
    assert "date_from" in response.json()["detail"]


def test_spa_path_cannot_escape_distribution_directory():
    response = client.get("/%2e%2e/%2e%2e/README.md")
    assert response.status_code == 404


def test_unknown_api_and_wrong_method_use_problem_details():
    missing = client.get("/api/v1/does-not-exist")
    assert missing.status_code == 404
    assert missing.headers["content-type"].startswith("application/problem+json")
    assert missing.json()["status"] == 404

    wrong_method = client.post("/api/v1/meta")
    assert wrong_method.status_code == 405
    assert wrong_method.json()["status"] == 405


def test_oversized_request_is_rejected_before_json_parsing():
    response = client.post(
        "/api/v1/ai/ask",
        content=b"x" * 40_000,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "Request body exceeds the configured limit."


def test_oversized_chunked_request_is_rejected_by_actual_bytes():
    response = client.post(
        "/api/v1/ai/ask",
        content=(chunk for chunk in (b"x" * 20_000, b"y" * 20_000)),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413


def test_openapi_has_explicit_success_and_error_contracts():
    schema = app.openapi()
    operations = [
        operation
        for path in schema["paths"].values()
        for method, operation in path.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]
    assert operations
    for operation in operations:
        response = operation["responses"]["200"]
        content = response.get("content", {})
        if "application/json" in content:
            assert content["application/json"].get("schema") not in ({}, None)
        assert "422" in operation["responses"]
    csv = schema["paths"]["/api/v1/ml/dataset.csv"]["get"]["responses"]["200"]
    assert "text/csv" in csv["content"]
