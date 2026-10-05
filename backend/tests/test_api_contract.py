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


def test_model_info_conforms_to_explicit_dto(monkeypatch):
    from app.schemas import ModelInfoAvailable, ModelInfoUnavailable

    # Loaded model -> the "available" DTO validates the payload shape.
    bundle = {
        "meta": {
            "model_version": 3,
            "n_shots": 657387,
            "seasons": ["2023-24", "2024-25", "2025-26"],
            "brier": 0.225,
            "auc": 0.66,
        },
        "feature_columns": ["distance", "angle"],
        "delta_distribution": [],
        "evaluation": {"winner": "hist_gradient_boosting"},
    }
    monkeypatch.setattr("app.routers.ml.ml.load_model", lambda: bundle)
    payload = client.get("/api/v1/ml/model-info").json()
    validated = ModelInfoAvailable.model_validate(payload)
    assert validated.available is True
    assert validated.model_version == 3
    assert validated.metrics.brier == 0.225

    # No model -> the "unavailable" DTO validates.
    monkeypatch.setattr("app.routers.ml.ml.load_model", lambda: None)
    unavailable = client.get("/api/v1/ml/model-info").json()
    validated_missing = ModelInfoUnavailable.model_validate(unavailable)
    assert validated_missing.available is False
    assert validated_missing.reason


def test_model_info_openapi_uses_named_schemas():
    schema = app.openapi()
    response = schema["paths"]["/api/v1/ml/model-info"]["get"]["responses"]["200"]
    body = response["content"]["application/json"]["schema"]
    refs = str(body)
    assert "ModelInfoAvailable" in refs and "ModelInfoUnavailable" in refs
    assert "ModelMetrics" in schema["components"]["schemas"]


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
    future_season = client.get("/api/v1/players/1/summary?season=2099-00")
    assert future_season.status_code == 422
    blank_search = client.get("/api/v1/players/search?q=%20%20")
    assert blank_search.status_code == 422


def test_meta_is_fast_local_metadata_and_advertises_preseason(monkeypatch):
    monkeypatch.setattr("app.routers.league.current_season", lambda: "2026-27")
    monkeypatch.setattr("app.routers.league.api.cached_latest_team_game_date", lambda _season: "2026-10-12")
    response = client.get("/api/v1/meta")
    assert response.status_code == 200
    payload = response.json()
    assert payload["season_types"] == ["Pre Season", "Regular Season", "Playoffs"]
    assert payload["data_through"] == "2026-10-12"


def test_meta_allows_cold_cache_without_an_upstream_call(monkeypatch):
    monkeypatch.setattr("app.routers.league.api.cached_latest_team_game_date", lambda _season: None)
    response = client.get("/api/v1/meta")
    assert response.status_code == 200
    assert response.json()["data_through"] is None


def test_player_routes_accept_preseason_season_type(monkeypatch):
    monkeypatch.setattr(
        "app.routers.players.players.summary",
        lambda player_id, season, season_type: {
            "player_id": player_id, "season": season, "season_type": season_type,
        },
    )
    response = client.get(
        "/api/v1/players/1/summary?season=2026-27&season_type=Pre%20Season"
    )
    assert response.status_code == 200
    assert response.json()["season_type"] == "Pre Season"


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


def test_ai_context_rejects_boolean_player_id_and_future_season():
    boolean_id = client.post("/api/v1/ai/ask", json={
        "question": "How is he playing?", "context": {"player_id": True},
    })
    assert boolean_id.status_code == 422
    assert "context.player_id" in boolean_id.json()["detail"]

    future = client.post("/api/v1/ai/ask", json={
        "question": "How is he playing?", "context": {
            "player_id": 23, "season": "2027-28", "season_type": "Pre Season",
        },
    })
    assert future.status_code == 422
    assert "context.season" in future.json()["detail"]


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
