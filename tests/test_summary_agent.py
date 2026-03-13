"""Tests for LocalSummaryAgent."""

import pytest
from unittest.mock import MagicMock, patch

from core.node.node_manager import (
    LocalSummaryAgent, Message, DEFAULT_SUMMARY_MODEL,
    SUMMARY_MIN_MESSAGES, SUMMARY_IMPORTANCE, SUMMARY_BATCH_SIZE,
)


class MockOllamaClient:
    """Mock Ollama client for testing."""

    def __init__(self, host=None):
        self.host = host

    def chat(self, model, messages):
        return {"message": {"content": "Test summary: topics discussed, decisions made."}}


class FailingOllamaClient:
    """Mock Ollama client that raises exceptions."""

    def __init__(self, host=None):
        self.host = host

    def chat(self, model, messages):
        raise ConnectionError("Ollama not available")


@pytest.mark.unit
def test_local_summary_agent_init():
    """Test LocalSummaryAgent initializes with correct defaults."""
    with patch("ollama.Client", MockOllamaClient):
        agent = LocalSummaryAgent(agent_id="test_summarizer")

    assert agent.agent_id == "test_summarizer"
    assert agent.name == "SummaryCourier"
    assert agent.model == DEFAULT_SUMMARY_MODEL
    assert agent.client is not None


@pytest.mark.unit
def test_local_summary_agent_always_uses_localhost():
    """Test that LocalSummaryAgent always connects to localhost."""
    with patch("ollama.Client", MockOllamaClient) as mock_cls:
        agent = LocalSummaryAgent(agent_id="test_summarizer")

    assert agent.LOCAL_HOST == "http://localhost:11434"


@pytest.mark.unit
def test_local_summary_agent_custom_model():
    """Test LocalSummaryAgent with custom model."""
    with patch("ollama.Client", MockOllamaClient):
        agent = LocalSummaryAgent(
            agent_id="test_summarizer",
            model="qwen2:1.5b",
        )

    assert agent.model == "qwen2:1.5b"


@pytest.mark.unit
async def test_summarize_conversation():
    """Test summarize_conversation returns summary text."""
    with patch("ollama.Client", MockOllamaClient):
        agent = LocalSummaryAgent(agent_id="test_summarizer")

    messages = [
        Message(sender="alice", content="How should we handle routing?"),
        Message(sender="bot", content="I suggest hash-based approach."),
        Message(sender="bob", content="Agreed, but we need fallback logic."),
    ]

    result = await agent.summarize_conversation(messages)
    assert "Test summary" in result


@pytest.mark.unit
async def test_summarize_empty_messages():
    """Test summarize_conversation with empty list."""
    with patch("ollama.Client", MockOllamaClient):
        agent = LocalSummaryAgent(agent_id="test_summarizer")

    result = await agent.summarize_conversation([])
    assert "No messages" in result


@pytest.mark.unit
async def test_summarize_with_no_client():
    """Test summarize_conversation when client is unavailable."""
    with patch("ollama.Client", side_effect=Exception("Connection refused")):
        agent = LocalSummaryAgent(agent_id="test_summarizer")

    assert agent.client is None
    result = await agent.summarize_conversation([
        Message(sender="alice", content="Hello"),
    ])
    assert "unavailable" in result.lower()


@pytest.mark.unit
async def test_summarize_with_failing_client():
    """Test summarize_conversation when LLM call fails."""
    with patch("ollama.Client", FailingOllamaClient):
        agent = LocalSummaryAgent(agent_id="test_summarizer")

    messages = [
        Message(sender="alice", content="Hello"),
    ]
    result = await agent.summarize_conversation(messages)
    assert "unavailable" in result.lower() or "Summary" in result


@pytest.mark.unit
async def test_generate_response_delegates_to_summarize():
    """Test generate_response satisfies BaseAgent interface."""
    with patch("ollama.Client", MockOllamaClient):
        agent = LocalSummaryAgent(agent_id="test_summarizer")

    messages = [
        Message(sender="alice", content="Test message"),
    ]
    result = await agent.generate_response("ignored", context=messages)
    assert "Test summary" in result
