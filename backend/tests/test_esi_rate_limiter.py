"""Tests for ESI client and token pool (updated for rate_limiter refactor)."""

from app.tools.esi_client import EsiClient, TokenPool


class TestTokenPool:
    def test_add_and_get(self):
        pool = TokenPool()
        pool.add_token("token1")
        assert pool.count == 1
        result = pool.get_next()
        assert result == "token1"

    def test_round_robin(self):
        pool = TokenPool()
        pool.add_token("token1")
        pool.add_token("token2")
        r1 = pool.get_next()
        r2 = pool.get_next()
        assert r1 == "token1"
        assert r2 == "token2"

    def test_no_duplicate_tokens(self):
        pool = TokenPool()
        pool.add_token("token1")
        pool.add_token("token1")
        assert pool.count == 1

    def test_empty_pool(self):
        pool = TokenPool()
        assert pool.get_next() is None
        assert pool.count == 0


class TestEsiClient:
    def test_client_has_required_methods(self):
        client = EsiClient()
        methods = [
            "get_market_orders",
            "get_all_market_orders",
            "get_market_history",
            "verify_character",
            "get_character_assets",
            "get_character_wallet",
            "get_character_orders",
            "get_character_transactions",
        ]
        for m in methods:
            assert hasattr(client, m), f"Missing method: {m}"

    def test_add_token_to_pool(self):
        client = EsiClient()
        client.add_token("test_token")
        assert client._token_pool.count == 1

    def test_has_rate_manager(self):
        client = EsiClient()
        assert hasattr(client, "_rate_manager")
        assert hasattr(client, "rate_stats")

    def test_rate_stats_returns_dict(self):
        client = EsiClient()
        stats = client.rate_stats
        assert "total_requests" in stats
        assert "total_429_hits" in stats
        assert "buckets" in stats
