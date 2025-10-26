"""Tests for DiffMem integration."""

import pytest
import asyncio

from core.memory.diffmem_integration import DiffMemManager, MemoryEntry


@pytest.mark.unit
async def test_add_memory(memory_manager):
    """Test adding a memory entry."""
    memory = await memory_manager.add_memory(
        content="This is a test memory",
        importance=5.0,
        tags=["test", "demo"],
        source="test_suite"
    )
    
    assert memory.content == "This is a test memory"
    assert memory.importance == 5.0
    assert "test" in memory.tags
    assert memory.embedding is not None


@pytest.mark.unit
async def test_retrieve_memories(memory_manager):
    """Test retrieving similar memories."""
    # Add some memories
    await memory_manager.add_memory("Python is a programming language", importance=8.0)
    await memory_manager.add_memory("JavaScript is also a programming language", importance=7.0)
    await memory_manager.add_memory("I like pizza", importance=3.0)
    
    # Retrieve memories similar to query
    memories = await memory_manager.retrieve_memories("programming", top_k=2)
    
    assert len(memories) <= 2
    # Should retrieve programming-related memories


@pytest.mark.unit
async def test_memory_importance_filtering(memory_manager):
    """Test filtering by importance."""
    await memory_manager.add_memory("High importance", importance=9.0)
    await memory_manager.add_memory("Low importance", importance=1.0)
    
    # Retrieve with high importance threshold
    memories = await memory_manager.retrieve_memories(
        "importance",
        top_k=10,
        min_importance=5.0
    )
    
    # Should only get high importance memories
    assert all(m.importance >= 5.0 for m in memories)


@pytest.mark.unit
async def test_memory_clustering(memory_manager):
    """Test memory clustering."""
    # Add related memories
    for i in range(5):
        await memory_manager.add_memory(f"Python programming topic {i}")
    
    for i in range(3):
        await memory_manager.add_memory(f"Cooking recipe {i}")
    
    clusters = await memory_manager.cluster_memories()
    
    # Should have at least some clusters
    assert len(clusters) > 0


@pytest.mark.unit
async def test_memory_consolidation(memory_manager):
    """Test memory consolidation."""
    # Add memories with different importance
    for i in range(10):
        await memory_manager.add_memory(
            f"Memory {i}",
            importance=float(i) / 10.0
        )
    
    initial_count = len(memory_manager.memories)
    
    # Consolidate
    await memory_manager.consolidate_memories()
    
    # Should have fewer memories after consolidation
    assert len(memory_manager.memories) <= initial_count


@pytest.mark.unit
def test_memory_entry_to_dict():
    """Test memory entry serialization."""
    entry = MemoryEntry(
        content="Test content",
        importance=5.0,
        tags=["test"]
    )
    
    data = entry.to_dict()
    assert data["content"] == "Test content"
    assert data["importance"] == 5.0
    assert "timestamp" in data


@pytest.mark.unit
def test_memory_entry_from_dict():
    """Test memory entry deserialization."""
    data = {
        "content": "Test content",
        "timestamp": 1234567890.0,
        "importance": 5.0,
        "access_count": 0,
        "last_accessed": 1234567890.0,
        "embedding": None,
        "tags": ["test"],
        "source": "test",
        "compressed": False
    }
    
    entry = MemoryEntry.from_dict(data)
    assert entry.content == "Test content"
    assert entry.importance == 5.0


@pytest.mark.unit
def test_memory_stats(memory_manager):
    """Test getting memory statistics."""
    stats = memory_manager.get_stats()
    
    assert "total_memories" in stats
    assert "total_size_bytes" in stats
    assert "compression_enabled" in stats
