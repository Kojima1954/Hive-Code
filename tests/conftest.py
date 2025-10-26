"""Pytest fixtures for testing."""

import pytest
import asyncio
import redis.asyncio as redis
from pathlib import Path
import tempfile
import shutil

from core.node.node_manager import HumanAINode
from core.memory.diffmem_integration import DiffMemManager
from core.security.encryption import HybridEncryption


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def redis_client():
    """Create a Redis client for testing."""
    client = await redis.from_url(
        "redis://localhost:6379",
        encoding="utf-8",
        decode_responses=True
    )
    
    # Clean test data
    await client.flushdb()
    
    yield client
    
    # Cleanup
    await client.flushdb()
    await client.close()


@pytest.fixture
def temp_storage():
    """Create temporary storage directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def memory_manager(temp_storage):
    """Create a DiffMemManager instance."""
    return DiffMemManager(storage_path=temp_storage)


@pytest.fixture
async def node(redis_client, memory_manager):
    """Create a HumanAINode instance."""
    node = HumanAINode(
        node_id="test_node",
        redis_client=redis_client,
        memory_manager=memory_manager
    )
    yield node
    await node.stop_listener()


@pytest.fixture
def encryption():
    """Create a HybridEncryption instance."""
    return HybridEncryption()
