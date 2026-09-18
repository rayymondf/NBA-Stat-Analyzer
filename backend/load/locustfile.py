"""Representative read-heavy workload for a warm NBA Stat Analyzer instance."""

from __future__ import annotations

import os

from locust import FastHttpUser, between, task


class AnalyticsUser(FastHttpUser):
    wait_time = between(0.8, 2.5)
    player_id = int(os.getenv("LOAD_PLAYER_ID", "201939"))

    def on_start(self) -> None:
        response = self.client.get("/api/v1/meta", name="GET /api/v1/meta")
        payload = response.json() if response.ok else {}
        self.season = os.getenv("LOAD_SEASON", payload.get("current_season", "2025-26"))

    @task(5)
    def player_summary(self) -> None:
        self.client.get(
            f"/api/v1/players/{self.player_id}/summary?season={self.season}",
            name="GET /api/v1/players/:id/summary",
        )

    @task(3)
    def player_overview(self) -> None:
        self.client.get(
            f"/api/v1/players/{self.player_id}/overview?season={self.season}",
            name="GET /api/v1/players/:id/overview",
        )

    @task(2)
    def player_shooting(self) -> None:
        self.client.get(
            f"/api/v1/players/{self.player_id}/shooting?season={self.season}",
            name="GET /api/v1/players/:id/shooting",
        )

    @task(1)
    def model_info(self) -> None:
        self.client.get("/api/v1/ml/model-info", name="GET /api/v1/ml/model-info")

    @task(1)
    def health(self) -> None:
        self.client.get("/health/ready", name="GET /health/ready")
