"""Tests for node manager."""

import pytest
import asyncio

from core.node.node_manager import (
    HumanAINode, ParticipantType, Message, NodeParticipant, OllamaAgent
)


@pytest.mark.unit
async def test_add_human_participant(node):
    """Test adding a human participant."""
    participant = await node.add_human_participant(
        user_id="user_123",
        name="Test User"
    )
    
    assert participant.id == "user_123"
    assert participant.name == "Test User"
    assert participant.type == ParticipantType.HUMAN
    assert "user_123" in node.participants


@pytest.mark.unit
async def test_create_ai_agent(node):
    """Test creating an AI agent."""
    agent = await node.create_ai_agent(
        agent_id="agent_1",
        name="TestBot",
        model="llama2"
    )
    
    assert agent.agent_id == "agent_1"
    assert agent.name == "TestBot"
    assert "agent_1" in node.agents
    assert "agent_1" in node.participants


@pytest.mark.unit
async def test_message_encryption(node):
    """Test message encryption and decryption."""
    original_content = "This is a secret message"
    
    encrypted = node.encrypt_message(original_content)
    assert encrypted != original_content
    
    decrypted = node.decrypt_message(encrypted)
    assert decrypted == original_content


@pytest.mark.unit
async def test_process_message(node):
    """Test processing a message."""
    await node.add_human_participant("user_1", "Alice")
    
    message = await node.process_message(
        sender_id="user_1",
        content="Hello, world!",
        encrypt=False
    )
    
    assert message.sender == "user_1"
    assert message.content == "Hello, world!"
    assert len(node.message_queue) > 0


@pytest.mark.unit
async def test_message_to_dict():
    """Test message serialization."""
    message = Message(
        sender="user_1",
        content="Test message"
    )
    
    message_dict = message.to_dict()
    assert message_dict["sender"] == "user_1"
    assert message_dict["content"] == "Test message"
    assert "timestamp" in message_dict


@pytest.mark.unit
async def test_message_from_dict():
    """Test message deserialization."""
    data = {
        "sender": "user_1",
        "content": "Test message",
        "timestamp": 1234567890.0,
        "message_type": "text",
        "metadata": {},
        "encrypted": False
    }
    
    message = Message.from_dict(data)
    assert message.sender == "user_1"
    assert message.content == "Test message"


@pytest.mark.unit
async def test_get_conversation_history(node):
    """Test getting conversation history."""
    await node.add_human_participant("user_1", "Alice")
    
    # Send multiple messages
    for i in range(5):
        await node.process_message("user_1", f"Message {i}")
    
    history = await node.get_conversation_history(limit=3)
    assert len(history) == 3
    assert history[-1].content == "Message 4"


@pytest.mark.unit
async def test_node_stats(node):
    """Test getting node statistics."""
    await node.add_human_participant("user_1", "Alice")
    await node.create_ai_agent("agent_1", "Bot")
    
    stats = node.get_stats()
    assert stats["node_id"] == "test_node"
    assert stats["participants"] == 2
    assert stats["human_participants"] == 1
    assert stats["ai_agents"] == 1


@pytest.mark.unit
async def test_node_summary(node):
    """Test generating node summary."""
    await node.add_human_participant("user_1", "Alice")
    
    summary = await node.generate_node_summary()
    assert "test_node" in summary
    assert "Total Participants: 1" in summary
