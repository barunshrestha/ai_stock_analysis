"""Cross-user isolation (IDOR) tests against the real database.

Assumes DATABASE_URL points at a disposable dev database, like the other route tests.
Each run creates two throwaway users and deletes them afterwards (their rows cascade).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.auth import CurrentUser
from backend.deps import _db_or_none
from backend.main import app


@pytest.fixture(scope="module")
def db():
    manager = _db_or_none()
    if manager is None:
        pytest.skip("Database unavailable")
    return manager


@pytest.fixture
def users(db):
    suffix = uuid.uuid4().hex[:10]
    alice = CurrentUser(id=f"test_alice_{suffix}", email=None, role="user")
    bob = CurrentUser(id=f"test_bob_{suffix}", email=None, role="user")
    for u in (alice, bob):
        db.upsert_user(u.id, None)
    yield alice, bob

    from sqlalchemy import text

    with db.engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE id IN (:a, :b)"), {"a": alice.id, "b": bob.id})


@pytest.fixture
def client():
    return TestClient(app)


def _trade_payload(ticker: str = "ISOL") -> dict:
    today = date.today()
    return {
        "strategy_type": "cash_secured_put",
        "ticker": ticker,
        "legs": [
            {"leg_index": 1, "option_type": "put", "side": "sell_to_open", "strike": 50, "premium_per_contract": 1.25}
        ],
        "contracts": 1,
        "executed_at": datetime.combine(today, datetime.min.time()).isoformat(),
        "expiration_date": (today + timedelta(days=30)).isoformat(),
        "net_credit_debit": 1.25,
    }


class TestPortfolioIsolation:
    def test_other_users_portfolio_is_invisible(self, client, users, signed_in_user, db):
        alice, bob = users

        signed_in_user.user = alice
        created = client.post("/api/portfolio/portfolios", json={"name": "Alice Growth"})
        assert created.status_code == 201
        alice_pid = created.json()["id"]
        assert db.add_to_portfolio("AAPL", alice_pid)

        signed_in_user.user = bob
        names = [p["name"] for p in client.get("/api/portfolio/portfolios").json()["portfolios"]]
        assert "Alice Growth" not in names
        assert client.get(f"/api/portfolio?portfolio_id={alice_pid}").status_code == 404
        assert client.get(f"/api/portfolio/grid?portfolio_id={alice_pid}").status_code == 404
        assert client.delete(f"/api/portfolio/AAPL?portfolio_id={alice_pid}").status_code == 404
        assert client.get("/api/news/portfolio").json()["symbols"] == []

        signed_in_user.user = alice
        assert client.get(f"/api/portfolio?portfolio_id={alice_pid}").json()["symbols"] == ["AAPL"]

    def test_same_portfolio_name_allowed_per_user(self, client, users, signed_in_user):
        alice, bob = users
        for u in (alice, bob):
            signed_in_user.user = u
            assert client.post("/api/portfolio/portfolios", json={"name": "Income"}).status_code == 201
        assert client.post("/api/portfolio/portfolios", json={"name": "Income"}).status_code == 409

    def test_new_user_gets_own_default_portfolio(self, client, users, signed_in_user):
        alice, bob = users
        signed_in_user.user = alice
        alice_default = client.get("/api/portfolio").json()["portfolio_id"]
        signed_in_user.user = bob
        bob_default = client.get("/api/portfolio").json()
        assert bob_default["portfolio_id"] != alice_default
        assert bob_default["symbols"] == []


class TestOptionsIsolation:
    @patch("backend.routers.options.options_advisory_service.build_advisory", return_value={})
    def test_other_users_trade_is_404(self, _advisory, client, users, signed_in_user):
        alice, bob = users

        signed_in_user.user = alice
        res = client.post("/api/options/trades", json=_trade_payload())
        assert res.status_code == 200, res.text
        trade_id = res.json()["id"]

        signed_in_user.user = bob
        assert all(t["id"] != trade_id for t in client.get("/api/options/trades").json()["trades"])
        assert client.get(f"/api/options/trades/{trade_id}").status_code == 404
        assert client.patch(f"/api/options/trades/{trade_id}", json={"contracts": 5}).status_code == 404
        assert client.patch(
            f"/api/options/trades/{trade_id}/close",
            json={"close_net_per_contract": 0.1, "closed_at": datetime.now().isoformat()},
        ).status_code == 404
        assert client.delete(f"/api/options/trades/{trade_id}").status_code == 404

        signed_in_user.user = alice
        assert client.get(f"/api/options/trades/{trade_id}").status_code == 200

    def test_ticker_notes_are_per_user(self, client, users, signed_in_user):
        alice, bob = users
        signed_in_user.user = alice
        assert client.put("/api/options/ticker-notes/ISOL", json={"content": "alice only"}).status_code == 200

        signed_in_user.user = bob
        assert client.get("/api/options/ticker-notes/ISOL").json()["content"] == ""
        assert client.put("/api/options/ticker-notes/ISOL", json={"content": "bob's"}).status_code == 200

        signed_in_user.user = alice
        assert client.get("/api/options/ticker-notes/ISOL").json()["content"] == "alice only"
