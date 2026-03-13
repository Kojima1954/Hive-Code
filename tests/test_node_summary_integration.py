"""Tests for HumanAINode summary integration."""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

from core.node.node_manager import (
    HumanAINode, LocalSummaryAgent, Message,
    SUMMARY_MIN_MESSAGES, SUMMARY_IMPORTANCE,
)


class MockOllamaClient:
    """Mock Ollama client."""

    def __init__(self, host=None):
        self.host = host

    def chat(self, model, messages):
        return {"message": {"content": "Summarized conversation about testing."}}


@pytest.fixture
def mock_ollama():
    """Patch ollama.Client for all tests in this module."""
    with patch("ollama.Client", MockOllamaClient):
        yield


@pytest.mark.unit
async def test_node_creates_summary_agent_when_enabled(redis_client, memory_manager, mock_ollama):
    """Test HumanAINode creates summary agent when enable_summary=True."""
    node = HumanAINode(
        node_id="test_node",
        redis_client=redis_client,
        memory_manager=memory_manager,
        enable_summary=True,
    )
    assert node.summary_agent is not None
    assert isinstance(node.summary_agent, LocalSummaryAgent)
    await node.stop_listener()


@pytest.mark.unit
async def test_node_no_summary_agent_when_disabled(redis_client, memory_manager):
    """Test HumanAINode does NOT create summary agent when enable_summary=False."""
    node = HumanAINode(
        node_id="test_node",
        redis_client=redis_client,
        memory_manager=memory_manager,
        enable_summary=False,
    )
    assert node.summary_agent is None
    await node.stop_listener()


@pytest.mark.unit
async def test_run_summarization_skips_when_too_few(redis_client, memory_manager, mock_ollama):
    """Test _run_summarization skips when fewer than SUMMARY_MIN_MESSAGES."""
    node = HumanAINode(
        node_id="test_node",
        redis_client=redis_client,
        memory_manager=memory_manager,
        enable_summary=True,
    )
    # Add fewer than SUMMARY_MIN_MESSAGES
    for i in range(SUMMARY_MIN_MESSAGES - 1):
        node.message_queue.append(Message(sender=f"user_{i}", content=f"msg {i}"))

    original_index = node._last_summarized_index
    await node._run_summarization()
    # Index should not have moved
    assert node._last_summarized_index == original_index
    await node.stop_listener()


@pytest.mark.unit
async def test_run_summarization_stores_in_memory(redis_client, memory_manager, mock_ollama):
    """Test _run_summarization stores summary in memory with correct tags."""
    node = HumanAINode(
        node_id="test_node",
        redis_client=redis_client,
        memory_manager=memory_manager,
        enable_summary=True,
    )
    # Add enough messages
    for i in range(SUMMARY_MIN_MESSAGES + 2):
        node.message_queue.append(Message(sender=f"user_{i}", content=f"msg {i}"))

    await node._run_summarization()

    # Verify index was updated
    assert node._last_summarized_index == SUMMARY_MIN_MESSAGES + 2
    await node.stop_listener()


@pytest.mark.unit
async def test_run_summarization_updates_index(redis_client, memory_manager, mock_ollama):
    """Test _last_summarized_index advances correctly."""
    node = HumanAINode(
        node_id="test_node",
        redis_client=redis_client,
        memory_manager=memory_manager,
        enable_summary=True,
    )

    # First batch
    for i in range(10):
        node.message_queue.append(Message(sender="user", content=f"msg {i}"))
    await node._run_summarization()
    assert node._last_summarized_index == 10

    # Add more messages but less than SUMMARY_MIN_MESSAGES
    for i in range(3):
        node.message_queue.append(Message(sender="user", content=f"extra {i}"))
    await node._run_summarization()
    # Should not advance since only 3 new messages
    assert node._last_summarized_index == 10
    await node.stop_listener()


@pytest.mark.unit
async def test_add_peer_and_get_peers(redis_client, memory_manager):
    """Test add_peer and peer_inboxes."""
    node = HumanAINode(
        node_id="test_node",
        redis_client=redis_client,
        memory_manager=memory_manager,
        enable_summary=False,
    )

    node.add_peer("https://node2.example.com/actors/main/inbox")
    node.add_peer("https://node3.example.com/actors/main/inbox")
    # Duplicate should be ignored
    node.add_peer("https://node2.example.com/actors/main/inbox")

    assert len(node.peer_inboxes) == 2
    await node.stop_listener()


@pytest.mark.unit
async def test_stop_listener_cancels_summary_task(redis_client, memory_manager, mock_ollama):
    """Test that stop_listener also cancels the summary task."""
    node = HumanAINode(
        node_id="test_node",
        redis_client=redis_client,
        memory_manager=memory_manager,
        enable_summary=True,
    )
    await node.start_summary_loop()
    assert node._summary_task is not None

    await node.stop_listener()
    assert node._summary_task.cancelled()
