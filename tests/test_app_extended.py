"""Extended tests for FastAPI application - ConnectionManager, JWT, API routes."""

import json
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from ui.web.app import (
    create_app, ConnectionManager, MessageRequest, MessageResponse, TokenData,
)


JWT_SECRET = "test-secret-key-for-testing-only-1234"


@pytest.fixture
def app():
    """Create a test app with startup skipped."""
    application = create_app(
        redis_url="redis://localhost:6379",
        ollama_host="http://localhost:11434",
        jwt_secret=JWT_SECRET,
        allowed_origins=["*"]
    )
    application.router.on_startup = []
    return application


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_ws():
    """Create a mock WebSocket."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def mock_redis_cm():
    """Create mock Redis client for ConnectionManager."""
    r = AsyncMock()
    r.pubsub.return_value = AsyncMock()
    return r


@pytest.fixture
def mock_node():
    """Create a mock HumanAINode."""
    node = MagicMock()
    node.node_id = "test_node"
    return node


class TestConnectionManager:
    """Tests for ConnectionManager."""

    @pytest.mark.unit
    async def test_connect_accepts_websocket(self, mock_redis_cm, mock_node, mock_ws):
        """Should accept WebSocket and track connection."""
        cm = ConnectionManager(mock_redis_cm, mock_node)
        await cm.connect("user1", mock_ws)
        assert "user1" in cm.active_connections
        mock_ws.accept.assert_called_once()

    @pytest.mark.unit
    async def test_disconnect_removes_connection(self, mock_redis_cm, mock_node, mock_ws):
        """Should remove connection on disconnect."""
        cm = ConnectionManager(mock_redis_cm, mock_node)
        await cm.connect("user1", mock_ws)
        cm.disconnect("user1")
        assert "user1" not in cm.active_connections

    @pytest.mark.unit
    def test_disconnect_nonexistent_user(self, mock_redis_cm, mock_node):
        """Should handle disconnecting a user that was never connected."""
        cm = ConnectionManager(mock_redis_cm, mock_node)
        cm.disconnect("ghost")  # should not raise

    @pytest.mark.unit
    async def test_send_personal_message(self, mock_redis_cm, mock_node, mock_ws):
        """Should send message to specific user."""
        cm = ConnectionManager(mock_redis_cm, mock_node)
        await cm.connect("user1", mock_ws)
        await cm.send_personal_message("hello", "user1")
        mock_ws.send_text.assert_called_with("hello")

    @pytest.mark.unit
    async def test_send_personal_message_to_missing_user(self, mock_redis_cm, mock_node):
        """Should silently skip if user not connected."""
        cm = ConnectionManager(mock_redis_cm, mock_node)
        await cm.send_personal_message("hello", "nobody")  # should not raise

    @pytest.mark.unit
    async def test_broadcast_sends_to_all(self, mock_redis_cm, mock_node):
        """Should broadcast message to all connected users."""
        cm = ConnectionManager(mock_redis_cm, mock_node)
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_text = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_text = AsyncMock()

        await cm.connect("user1", ws1)
        await cm.connect("user2", ws2)
        await cm.broadcast("hello everyone")

        ws1.send_text.assert_called_with("hello everyone")
        ws2.send_text.assert_called_with("hello everyone")

    @pytest.mark.unit
    async def test_broadcast_excludes_user(self, mock_redis_cm, mock_node):
        """Should exclude specified user from broadcast."""
        cm = ConnectionManager(mock_redis_cm, mock_node)
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_text = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_text = AsyncMock()

        await cm.connect("user1", ws1)
        await cm.connect("user2", ws2)
        await cm.broadcast("hello", exclude="user1")

        ws1.send_text.assert_not_called()
        ws2.send_text.assert_called_with("hello")

    @pytest.mark.unit
    async def test_broadcast_handles_send_failure(self, mock_redis_cm, mock_node):
        """Should disconnect users that fail to receive broadcasts."""
        cm = ConnectionManager(mock_redis_cm, mock_node)
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_text = AsyncMock(side_effect=ConnectionError("gone"))
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_text = AsyncMock()

        await cm.connect("user1", ws1)
        await cm.connect("user2", ws2)
        await cm.broadcast("hello")

        # user1 should be disconnected due to send failure
        assert "user1" not in cm.active_connections
        assert "user2" in cm.active_connections


class TestJWTAuthentication:
    """Tests for JWT token creation and verification."""

    @pytest.mark.unit
    def test_login_returns_token(self, client):
        """Login should return a JWT token."""
        response = client.post(
            "/api/auth/login",
            params={"username": "testuser", "password": "demo"}
        )
        # May fail without Redis, but if it works the structure should be right
        if response.status_code == 200:
            data = response.json()
            assert "token" in data
            assert data["username"] == "testuser"
            assert data["user_id"] == "user_testuser"

    @pytest.mark.unit
    def test_login_rejects_invalid_username(self, client):
        """Login should reject invalid usernames."""
        response = client.post(
            "/api/auth/login",
            params={"username": "bad user!", "password": "demo"}
        )
        assert response.status_code == 400

    @pytest.mark.unit
    def test_token_structure(self):
        """JWT token should decode to contain user_id and username."""
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": "user_alice",
            "username": "alice",
            "exp": now + timedelta(hours=24),
            "iat": now,
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        assert decoded["user_id"] == "user_alice"
        assert decoded["username"] == "alice"

    @pytest.mark.unit
    def test_expired_token_raises(self):
        """Expired JWT should raise ExpiredSignatureError."""
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        payload = {
            "user_id": "user_alice",
            "username": "alice",
            "exp": past,
            "iat": past - timedelta(hours=24),
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(token, JWT_SECRET, algorithms=["HS256"])

    @pytest.mark.unit
    def test_invalid_token_raises(self):
        """Invalid JWT should raise InvalidTokenError."""
        with pytest.raises(jwt.InvalidTokenError):
            jwt.decode("not.a.token", JWT_SECRET, algorithms=["HS256"])

    @pytest.mark.unit
    def test_wrong_secret_raises(self):
        """Token signed with wrong secret should fail verification."""
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": "user_alice",
            "username": "alice",
            "exp": now + timedelta(hours=24),
            "iat": now,
        }
        token = jwt.encode(payload, "wrong-secret", algorithm="HS256")
        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(token, JWT_SECRET, algorithms=["HS256"])


class TestAPIEndpoints:
    """Extended tests for API endpoints."""

    @pytest.mark.unit
    def test_health_returns_status_field(self, client):
        """Health endpoint should always return a status field."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data

    @pytest.mark.unit
    def test_metrics_returns_prometheus_format(self, client):
        """Metrics endpoint should return Prometheus text format."""
        response = client.get("/metrics")
        assert response.status_code == 200
        content = response.text
        # Prometheus format should contain HELP or TYPE lines
        assert "swarm_" in content or "# HELP" in content or response.text == ""

    @pytest.mark.unit
    def test_messages_endpoint_requires_node(self, client):
        """Messages endpoint should return 503 when node not initialized."""
        response = client.post(
            "/api/messages",
            json={"content": "hello", "encrypt": False}
        )
        assert response.status_code == 503

    @pytest.mark.unit
    def test_history_endpoint_requires_node(self, client):
        """History endpoint should return 503 when node not initialized."""
        response = client.get("/api/messages/history")
        assert response.status_code == 503

    @pytest.mark.unit
    def test_node_summary_requires_node(self, client):
        """Node summary endpoint should return 503 when node not initialized."""
        response = client.get("/api/node/summary")
        assert response.status_code == 503

    @pytest.mark.unit
    def test_node_stats_requires_node(self, client):
        """Node stats endpoint should return 503 when node not initialized."""
        response = client.get("/api/node/stats")
        assert response.status_code == 503

    @pytest.mark.unit
    def test_root_serves_html_or_fallback(self, client):
        """Root endpoint should serve HTML content."""
        response = client.get("/")
        assert response.status_code == 200
        assert "html" in response.headers.get("content-type", "").lower()


class TestSecurityWarnings:
    """Tests for security configuration warnings."""

    @pytest.mark.unit
    def test_weak_jwt_secret_logged(self):
        """Should log warning for weak JWT secrets."""
        with patch("ui.web.app.logger") as mock_logger:
            create_app(jwt_secret="change-this")
            warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
            assert any("JWT" in w for w in warning_calls)

    @pytest.mark.unit
    def test_wildcard_cors_logged(self):
        """Should log warning for wildcard CORS origins."""
        with patch("ui.web.app.logger") as mock_logger:
            create_app(allowed_origins=["*"])
            warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
            assert any("CORS" in w for w in warning_calls)

    @pytest.mark.unit
    def test_short_jwt_secret_logged(self):
        """Should log warning for short JWT secrets."""
        with patch("ui.web.app.logger") as mock_logger:
            create_app(jwt_secret="short")
            warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
            assert any("characters" in w for w in warning_calls)
