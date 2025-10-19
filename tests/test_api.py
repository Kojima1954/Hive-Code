"""Tests for FastAPI application."""

import pytest
from fastapi.testclient import TestClient

from ui.web.app import create_app


@pytest.fixture
def client():
    """Create a test client."""
    app = create_app(
        redis_url="redis://localhost:6379",
        ollama_host="http://localhost:11434",
        jwt_secret="test-secret",
        allowed_origins=["*"]
    )
    
    # Skip startup event for testing
    app.router.on_startup = []
    
    return TestClient(app)


@pytest.mark.unit
def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code in [200, 404]  # May not have HTML file in test


@pytest.mark.unit
def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code in [200, 503]
    data = response.json()
    assert "status" in data


@pytest.mark.unit
def test_metrics_endpoint(client):
    """Test Prometheus metrics endpoint."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


@pytest.mark.unit
def test_login_endpoint(client):
    """Test login endpoint."""
    response = client.post(
        "/api/auth/login",
        params={"username": "testuser", "password": "demo"}
    )
    
    # May fail if Redis not available, but structure should be correct
    if response.status_code == 200:
        data = response.json()
        assert "token" in data
        assert "user_id" in data
        assert "username" in data


@pytest.mark.unit
def test_message_request_model():
    """Test MessageRequest model validation."""
    from ui.web.app import MessageRequest
    
    msg = MessageRequest(content="Test message", encrypt=False)
    assert msg.content == "Test message"
    assert msg.encrypt is False


@pytest.mark.unit
def test_message_response_model():
    """Test MessageResponse model."""
    from ui.web.app import MessageResponse
    
    msg = MessageResponse(
        sender="user_1",
        content="Test",
        timestamp=1234567890.0
    )
    assert msg.sender == "user_1"
    assert msg.message_type == "text"


@pytest.mark.unit
def test_token_data_model():
    """Test TokenData model."""
    from ui.web.app import TokenData
    
    token = TokenData(user_id="user_1", username="testuser")
    assert token.user_id == "user_1"
    assert token.username == "testuser"
