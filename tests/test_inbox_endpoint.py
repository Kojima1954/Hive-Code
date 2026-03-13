"""Tests for ActivityPub inbox and summary API endpoints."""

import json
import pytest
from fastapi.testclient import TestClient

from ui.web.app import create_app


@pytest.fixture
def client():
    """Create a test client with startup skipped."""
    app = create_app(
        redis_url="redis://localhost:6379",
        ollama_host="http://localhost:11434",
        jwt_secret="test-secret",
        allowed_origins=["*"],
        summary_model="phi3:mini",
        summary_interval=300,
    )
    app.router.on_startup = []
    return TestClient(app)


@pytest.mark.unit
def test_activitypub_inbox_create_node_summary(client):
    """Test POST /actors/{id}/inbox with valid NodeSummary activity."""
    activity = {
        "type": "Create",
        "actor": "https://remote.example.com/actors/node2",
        "object": {
            "type": "Note",
            "content": json.dumps({
                "type": "NodeSummary",
                "node_id": "remote_node_2",
                "summary": "Discussion about routing algorithms.",
                "timestamp": 1700000000,
                "message_count": 10,
            }),
        },
    }
    response = client.post("/actors/main/inbox", json=activity)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"


@pytest.mark.unit
def test_activitypub_inbox_non_create_activity(client):
    """Test POST /actors/{id}/inbox with non-Create activity is ignored."""
    activity = {
        "type": "Follow",
        "actor": "https://remote.example.com/actors/node2",
        "object": "https://local.example.com/actors/main",
    }
    response = client.post("/actors/main/inbox", json=activity)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "ignored"


@pytest.mark.unit
def test_activitypub_inbox_non_summary_content(client):
    """Test POST /actors/{id}/inbox with non-NodeSummary content is ignored."""
    activity = {
        "type": "Create",
        "actor": "https://remote.example.com/actors/node2",
        "object": {
            "type": "Note",
            "content": "Just a plain text message, not JSON.",
        },
    }
    response = client.post("/actors/main/inbox", json=activity)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "ignored"


@pytest.mark.unit
def test_activitypub_actor_not_configured(client):
    """Test GET /actors/{id} returns 404 when federation not configured."""
    response = client.get("/actors/main")
    assert response.status_code == 404


@pytest.mark.unit
def test_summarize_endpoint_no_node(client):
    """Test POST /api/node/summarize returns 503 when node not initialized."""
    response = client.post("/api/node/summarize")
    assert response.status_code == 503


@pytest.mark.unit
def test_summaries_endpoint_no_node(client):
    """Test GET /api/node/summaries returns 503 when node not initialized."""
    response = client.get("/api/node/summaries")
    assert response.status_code == 503


@pytest.mark.unit
def test_federation_peers_endpoint_no_node(client):
    """Test POST /api/federation/peers returns 503 when node not initialized."""
    response = client.post("/api/federation/peers?inbox_url=https://example.com/inbox")
    assert response.status_code == 503
