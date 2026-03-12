"""Tests for rate limiting and DDoS protection."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.security.rate_limiting import (
    RateLimiter,
    DDoSProtection,
    RateLimitMiddleware,
    DEFAULT_BAN_DURATION,
    MAX_VIOLATIONS_BEFORE_BAN,
    DEFAULT_API_RATE_LIMIT,
    DEFAULT_WS_RATE_LIMIT,
    DEFAULT_METRICS_RATE_LIMIT,
)
from core.security.input_validation import ValidationError


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    client = AsyncMock()
    client.zremrangebyscore = AsyncMock()
    client.zcard = AsyncMock(return_value=0)
    client.zadd = AsyncMock()
    client.expire = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.setex = AsyncMock()
    client.incr = AsyncMock(return_value=1)
    return client


@pytest.fixture
def rate_limiter(mock_redis):
    """Create a RateLimiter instance."""
    return RateLimiter(mock_redis)


@pytest.fixture
def rate_limiter_fail_open(mock_redis):
    """Create a RateLimiter with fail_open=True."""
    return RateLimiter(mock_redis, fail_open=True)


@pytest.fixture
def ddos_protection(mock_redis):
    """Create a DDoSProtection instance."""
    return DDoSProtection(mock_redis)


class TestRateLimiter:
    """Tests for RateLimiter."""

    @pytest.mark.unit
    async def test_allows_request_within_limit(self, rate_limiter, mock_redis):
        """Request within rate limit should be allowed."""
        mock_redis.zcard.return_value = 5
        allowed, remaining = await rate_limiter.check_rate_limit("test-key", 10, 60)
        assert allowed is True
        assert remaining == 4

    @pytest.mark.unit
    async def test_blocks_request_exceeding_limit(self, rate_limiter, mock_redis):
        """Request exceeding rate limit should be blocked."""
        mock_redis.zcard.return_value = 10
        allowed, remaining = await rate_limiter.check_rate_limit("test-key", 10, 60)
        assert allowed is False
        assert remaining == 0

    @pytest.mark.unit
    async def test_removes_old_entries(self, rate_limiter, mock_redis):
        """Old entries outside the window should be removed."""
        mock_redis.zcard.return_value = 0
        await rate_limiter.check_rate_limit("test-key", 10, 60)
        mock_redis.zremrangebyscore.assert_called_once()

    @pytest.mark.unit
    async def test_adds_current_request_when_allowed(self, rate_limiter, mock_redis):
        """Current request timestamp should be recorded when allowed."""
        mock_redis.zcard.return_value = 0
        await rate_limiter.check_rate_limit("test-key", 10, 60)
        mock_redis.zadd.assert_called_once()
        mock_redis.expire.assert_called_once()

    @pytest.mark.unit
    async def test_does_not_add_when_blocked(self, rate_limiter, mock_redis):
        """No new entry should be added when rate limit exceeded."""
        mock_redis.zcard.return_value = 10
        await rate_limiter.check_rate_limit("test-key", 10, 60)
        mock_redis.zadd.assert_not_called()

    @pytest.mark.unit
    async def test_invalid_limit_raises_value_error(self, rate_limiter):
        """Non-positive limit should raise ValueError."""
        with pytest.raises(ValueError, match="positive"):
            await rate_limiter.check_rate_limit("test-key", 0, 60)
        with pytest.raises(ValueError, match="positive"):
            await rate_limiter.check_rate_limit("test-key", -1, 60)

    @pytest.mark.unit
    async def test_invalid_window_raises_value_error(self, rate_limiter):
        """Non-positive window should raise ValueError."""
        with pytest.raises(ValueError, match="positive"):
            await rate_limiter.check_rate_limit("test-key", 10, 0)
        with pytest.raises(ValueError, match="positive"):
            await rate_limiter.check_rate_limit("test-key", 10, -5)

    @pytest.mark.unit
    async def test_fail_closed_on_redis_error(self, rate_limiter, mock_redis):
        """Default behavior: reject requests when Redis fails."""
        mock_redis.zremrangebyscore.side_effect = ConnectionError("Redis down")
        allowed, remaining = await rate_limiter.check_rate_limit("test-key", 10, 60)
        assert allowed is False
        assert remaining == 0

    @pytest.mark.unit
    async def test_fail_open_on_redis_error(self, rate_limiter_fail_open, mock_redis):
        """Fail-open behavior: allow requests when Redis fails."""
        mock_redis.zremrangebyscore.side_effect = ConnectionError("Redis down")
        allowed, remaining = await rate_limiter_fail_open.check_rate_limit("test-key", 10, 60)
        assert allowed is True
        assert remaining == 10

    @pytest.mark.unit
    async def test_invalid_redis_key_fails_closed(self, rate_limiter):
        """Invalid Redis key should fail closed (rejected)."""
        allowed, remaining = await rate_limiter.check_rate_limit("key with spaces", 10, 60)
        assert allowed is False
        assert remaining == 0


class TestDDoSProtection:
    """Tests for DDoSProtection."""

    @pytest.mark.unit
    async def test_is_banned_returns_false_for_unbanned_ip(self, ddos_protection, mock_redis):
        """Unbanned IP should return False."""
        mock_redis.get.return_value = None
        assert await ddos_protection.is_banned("192.168.1.1") is False

    @pytest.mark.unit
    async def test_is_banned_returns_true_for_banned_ip(self, ddos_protection, mock_redis):
        """Banned IP should return True."""
        mock_redis.get.return_value = "Rate limit exceeded"
        assert await ddos_protection.is_banned("192.168.1.1") is True

    @pytest.mark.unit
    async def test_ban_ip_sets_redis_key(self, ddos_protection, mock_redis):
        """Banning an IP should set a key in Redis with TTL."""
        await ddos_protection.ban_ip("192.168.1.1", "Testing")
        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args
        assert args[0][1] == DEFAULT_BAN_DURATION
        assert args[0][2] == "Testing"

    @pytest.mark.unit
    async def test_check_request_allows_normal_traffic(self, ddos_protection, mock_redis):
        """Normal requests from unbanned IP should be allowed."""
        mock_redis.get.return_value = None  # not banned
        mock_redis.zcard.return_value = 0  # no prior requests
        result = await ddos_protection.check_request("192.168.1.1", "/api/test", 100, 60)
        assert result is True

    @pytest.mark.unit
    async def test_check_request_blocks_banned_ip(self, ddos_protection, mock_redis):
        """Requests from banned IPs should be blocked."""
        mock_redis.get.return_value = "banned"
        result = await ddos_protection.check_request("192.168.1.1", "/api/test", 100, 60)
        assert result is False

    @pytest.mark.unit
    async def test_check_request_blocks_rate_limited_ip(self, ddos_protection, mock_redis):
        """Requests exceeding rate limit should be blocked."""
        mock_redis.get.return_value = None  # not banned
        mock_redis.zcard.return_value = 100  # at limit
        mock_redis.incr.return_value = 1
        result = await ddos_protection.check_request("192.168.1.1", "/api/test", 100, 60)
        assert result is False

    @pytest.mark.unit
    async def test_auto_ban_after_repeated_violations(self, ddos_protection, mock_redis):
        """IP should be auto-banned after MAX_VIOLATIONS_BEFORE_BAN violations."""
        mock_redis.get.return_value = None  # not banned
        mock_redis.zcard.return_value = 100  # at limit
        mock_redis.incr.return_value = MAX_VIOLATIONS_BEFORE_BAN
        await ddos_protection.check_request("192.168.1.1", "/api/test", 100, 60)
        # Should have called setex to ban
        mock_redis.setex.assert_called_once()

    @pytest.mark.unit
    async def test_no_ban_before_threshold(self, ddos_protection, mock_redis):
        """IP should not be banned before reaching violation threshold."""
        mock_redis.get.return_value = None
        mock_redis.zcard.return_value = 100
        mock_redis.incr.return_value = MAX_VIOLATIONS_BEFORE_BAN - 1
        await ddos_protection.check_request("192.168.1.1", "/api/test", 100, 60)
        mock_redis.setex.assert_not_called()

    @pytest.mark.unit
    async def test_is_banned_handles_redis_error(self, ddos_protection, mock_redis):
        """Redis error during ban check should return False (fail open for reads)."""
        mock_redis.get.side_effect = ConnectionError("Redis down")
        result = await ddos_protection.is_banned("192.168.1.1")
        assert result is False

    @pytest.mark.unit
    async def test_ban_ip_handles_redis_error(self, ddos_protection, mock_redis):
        """Redis error during ban should not raise."""
        mock_redis.setex.side_effect = ConnectionError("Redis down")
        # Should not raise
        await ddos_protection.ban_ip("192.168.1.1")


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware."""

    @pytest.mark.unit
    def test_get_client_ip_direct(self):
        """Should return client host when no forwarded header."""
        mock_app = MagicMock()
        mock_redis = AsyncMock()
        middleware = RateLimitMiddleware(mock_app, mock_redis)

        request = MagicMock()
        request.headers = {}
        request.client.host = "10.0.0.1"
        assert middleware.get_client_ip(request) == "10.0.0.1"

    @pytest.mark.unit
    def test_get_client_ip_forwarded(self):
        """Should return first IP from X-Forwarded-For header."""
        mock_app = MagicMock()
        mock_redis = AsyncMock()
        middleware = RateLimitMiddleware(mock_app, mock_redis)

        request = MagicMock()
        request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
        assert middleware.get_client_ip(request) == "1.2.3.4"

    @pytest.mark.unit
    def test_get_client_ip_forwarded_single(self):
        """Should handle single IP in X-Forwarded-For."""
        mock_app = MagicMock()
        mock_redis = AsyncMock()
        middleware = RateLimitMiddleware(mock_app, mock_redis)

        request = MagicMock()
        request.headers = {"X-Forwarded-For": "1.2.3.4"}
        assert middleware.get_client_ip(request) == "1.2.3.4"

    @pytest.mark.unit
    def test_default_rules(self):
        """Should have sensible default rate limit rules."""
        mock_app = MagicMock()
        mock_redis = AsyncMock()
        middleware = RateLimitMiddleware(mock_app, mock_redis)

        assert "/api/" in middleware.rules
        assert "/ws/" in middleware.rules
        assert "/metrics" in middleware.rules
        assert middleware.rules["/api/"] == DEFAULT_API_RATE_LIMIT
        assert middleware.rules["/ws/"] == DEFAULT_WS_RATE_LIMIT
        assert middleware.rules["/metrics"] == DEFAULT_METRICS_RATE_LIMIT

    @pytest.mark.unit
    def test_custom_rules(self):
        """Should accept custom rate limit rules."""
        mock_app = MagicMock()
        mock_redis = AsyncMock()
        custom_rules = {"/custom/": (50, 30)}
        middleware = RateLimitMiddleware(mock_app, mock_redis, rules=custom_rules)
        assert middleware.rules == custom_rules
