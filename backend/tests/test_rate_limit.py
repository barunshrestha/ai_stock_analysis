"""Tests for the per-user AI generation rate limiter."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.auth import CurrentUser
from backend.main import app
from backend.rate_limit import SlidingWindowLimiter, ai_generation_limiter


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class TestSlidingWindowLimiter:
    def test_blocks_after_limit_and_reports_wait(self):
        clock = FakeClock()
        limiter = SlidingWindowLimiter(limit=2, window_seconds=60, clock=clock)
        assert limiter.try_acquire("u") is None
        clock.now += 10
        assert limiter.try_acquire("u") is None
        assert limiter.try_acquire("u") == 50

    def test_slot_frees_after_window(self):
        clock = FakeClock()
        limiter = SlidingWindowLimiter(limit=1, window_seconds=60, clock=clock)
        assert limiter.try_acquire("u") is None
        clock.now += 60
        assert limiter.try_acquire("u") is None

    def test_users_are_counted_separately(self):
        limiter = SlidingWindowLimiter(limit=1, window_seconds=60, clock=FakeClock())
        assert limiter.try_acquire("alice") is None
        assert limiter.try_acquire("bob") is None
        assert limiter.try_acquire("alice") is not None


class TestAiRouteLimit:
    def test_generation_over_budget_is_429(self, monkeypatch, signed_in_user):
        monkeypatch.setattr(ai_generation_limiter, "limit", 2)
        signed_in_user.user = CurrentUser(id="rate_limit_user", email=None, role="user")
        client = TestClient(app)
        structured = {"moat_score": 5, "confidence": "low", "strongest_pillar": "brand"}
        with (
            patch("backend.routers.ai.research_metrics_service.build_research_metrics", return_value={}),
            patch("backend.routers.ai.gemini_service.generate_moat_memo", return_value=("## m", structured, None)),
        ):
            codes = [client.post("/api/ai/moat", json={"symbol": "RLTEST"}).status_code for _ in range(3)]
        assert codes == [200, 200, 429]
