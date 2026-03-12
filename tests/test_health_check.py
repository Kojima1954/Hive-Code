"""Tests for health check module."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from core.monitoring.health_check import HealthChecker


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    client = AsyncMock()
    client.ping = AsyncMock(return_value=True)
    client.info = AsyncMock(return_value={
        "connected_clients": 5,
        "used_memory_human": "1.5M",
        "uptime_in_seconds": 3600,
    })
    return client


@pytest.fixture
def checker(mock_redis):
    """Create a HealthChecker with mock Redis."""
    return HealthChecker(redis_client=mock_redis)


@pytest.fixture
def checker_no_redis():
    """Create a HealthChecker without Redis."""
    return HealthChecker(redis_client=None)


class TestCheckRedis:
    """Tests for check_redis."""

    @pytest.mark.unit
    async def test_healthy_redis(self, checker, mock_redis):
        """Should return healthy status when Redis responds."""
        result = await checker.check_redis()
        assert result["status"] == "healthy"
        assert result["connected_clients"] == 5
        assert result["used_memory_human"] == "1.5M"
        assert result["uptime_seconds"] == 3600

    @pytest.mark.unit
    async def test_disabled_when_no_client(self, checker_no_redis):
        """Should return disabled when no Redis client configured."""
        result = await checker_no_redis.check_redis()
        assert result["status"] == "disabled"

    @pytest.mark.unit
    async def test_unhealthy_on_timeout(self, checker, mock_redis):
        """Should return unhealthy on Redis timeout."""
        mock_redis.ping.side_effect = asyncio.TimeoutError()
        result = await checker.check_redis()
        assert result["status"] == "unhealthy"
        assert "timeout" in result["message"].lower()

    @pytest.mark.unit
    async def test_unhealthy_on_connection_error(self, checker, mock_redis):
        """Should return unhealthy on Redis connection error."""
        mock_redis.ping.side_effect = ConnectionError("Connection refused")
        result = await checker.check_redis()
        assert result["status"] == "unhealthy"
        assert "Connection refused" in result["message"]


class TestCheckSystemMetrics:
    """Tests for check_system_metrics."""

    @pytest.mark.unit
    def test_returns_cpu_memory_disk(self, checker):
        """Should return CPU, memory, and disk metrics."""
        result = checker.check_system_metrics()
        assert "cpu_percent" in result
        assert "memory" in result
        assert "disk" in result
        assert "total" in result["memory"]
        assert "available" in result["memory"]
        assert "percent" in result["memory"]
        assert "total" in result["disk"]
        assert "free" in result["disk"]

    @pytest.mark.unit
    def test_handles_psutil_error(self, checker):
        """Should return error dict on psutil failure."""
        with patch("core.monitoring.health_check.psutil") as mock_psutil:
            mock_psutil.cpu_percent.side_effect = RuntimeError("No CPU")
            result = checker.check_system_metrics()
            assert "error" in result


class TestCheckUptime:
    """Tests for check_uptime."""

    @pytest.mark.unit
    def test_returns_uptime_info(self, checker):
        """Should return start time, current time, and uptime."""
        result = checker.check_uptime()
        assert "start_time" in result
        assert "current_time" in result
        assert "uptime_seconds" in result
        assert "uptime_human" in result
        assert isinstance(result["uptime_seconds"], int)
        assert result["uptime_seconds"] >= 0


class TestGetHealthStatus:
    """Tests for get_health_status."""

    @pytest.mark.unit
    async def test_healthy_overall_status(self, checker):
        """Should return healthy when all checks pass."""
        status = await checker.get_health_status()
        assert status["status"] == "healthy"
        assert "uptime" in status
        assert "system" in status
        assert "redis" in status
        assert "timestamp" in status

    @pytest.mark.unit
    async def test_degraded_when_redis_unhealthy(self, checker, mock_redis):
        """Should return degraded when Redis is unhealthy."""
        mock_redis.ping.side_effect = ConnectionError("down")
        status = await checker.get_health_status()
        assert status["status"] == "degraded"

    @pytest.mark.unit
    async def test_no_redis_key_without_client(self, checker_no_redis):
        """Should not include Redis status when no client configured."""
        status = await checker_no_redis.get_health_status()
        assert "redis" not in status
        assert status["status"] == "healthy"

    @pytest.mark.unit
    async def test_degraded_on_high_memory(self, checker):
        """Should warn on high memory usage."""
        with patch.object(checker, "check_system_metrics") as mock_sys:
            mock_sys.return_value = {
                "cpu_percent": 10,
                "memory": {"total": 100, "available": 5, "percent": 95, "used": 95},
                "disk": {"total": 100, "used": 50, "free": 50, "percent": 50},
            }
            status = await checker.get_health_status()
            assert status["status"] == "degraded"
            assert "High memory usage" in status.get("warnings", [])

    @pytest.mark.unit
    async def test_degraded_on_high_cpu(self, checker):
        """Should warn on high CPU usage."""
        with patch.object(checker, "check_system_metrics") as mock_sys:
            mock_sys.return_value = {
                "cpu_percent": 95,
                "memory": {"total": 100, "available": 50, "percent": 50, "used": 50},
                "disk": {"total": 100, "used": 50, "free": 50, "percent": 50},
            }
            status = await checker.get_health_status()
            assert status["status"] == "degraded"
            assert "High CPU usage" in status.get("warnings", [])

    @pytest.mark.unit
    async def test_degraded_on_high_disk(self, checker):
        """Should warn on high disk usage."""
        with patch.object(checker, "check_system_metrics") as mock_sys:
            mock_sys.return_value = {
                "cpu_percent": 10,
                "memory": {"total": 100, "available": 50, "percent": 50, "used": 50},
                "disk": {"total": 100, "used": 95, "free": 5, "percent": 95},
            }
            status = await checker.get_health_status()
            assert status["status"] == "degraded"
            assert "High disk usage" in status.get("warnings", [])

    @pytest.mark.unit
    async def test_unhealthy_on_system_error(self, checker):
        """Should return unhealthy when system metrics fail."""
        with patch.object(checker, "check_system_metrics") as mock_sys:
            mock_sys.return_value = {"error": "psutil crashed"}
            status = await checker.get_health_status()
            assert status["status"] == "unhealthy"


class TestIsHealthy:
    """Tests for is_healthy."""

    @pytest.mark.unit
    async def test_returns_true_when_healthy(self, checker):
        """Should return True when status is healthy."""
        assert await checker.is_healthy() is True

    @pytest.mark.unit
    async def test_returns_true_when_degraded(self, checker, mock_redis):
        """Should return True when status is degraded (still operational)."""
        mock_redis.ping.side_effect = ConnectionError("down")
        assert await checker.is_healthy() is True

    @pytest.mark.unit
    async def test_returns_false_when_unhealthy(self, checker):
        """Should return False when status is unhealthy."""
        with patch.object(checker, "check_system_metrics") as mock_sys:
            mock_sys.return_value = {"error": "critical failure"}
            assert await checker.is_healthy() is False
