"""DiffMem integration with Git-based versioning and embeddings."""

import asyncio
import hashlib
import json
import logging
import os
import threading
import time
import zlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from git import Repo
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

# Try to import sentence-transformers, fall back to hash-based embeddings
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logger.warning("sentence-transformers not available, using hash-based embeddings")

# Constants
DEFAULT_EMBEDDING_MODEL = 'all-MiniLM-L6-v2'
DEFAULT_MAX_SIZE_MB = 1000
DEFAULT_CONSOLIDATION_INTERVAL = 3600  # 1 hour in seconds
COMPRESSION_THRESHOLD_BYTES = 1024  # Compress content larger than 1KB
MEMORY_IMPORTANCE_THRESHOLD = 0.1  # Minimum importance to retain
MEMORY_DECAY_HALF_LIFE_DAYS = 30  # Importance decay half-life
DBSCAN_DEFAULT_EPS = 0.3
DBSCAN_DEFAULT_MIN_SAMPLES = 2


@dataclass
class MemoryEntry:
    """Represents a single memory entry with metadata."""
    
    content: str
    timestamp: float = field(default_factory=time.time)
    importance: float = 1.0
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    embedding: Optional[List[float]] = None
    tags: List[str] = field(default_factory=list)
    source: str = "unknown"
    compressed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryEntry':
        """Create from dictionary."""
        return cls(**data)


class DiffMemManager:
    """
    Memory manager with Git-based versioning, embeddings, and compression.
    """
    
    def __init__(
        self,
        storage_path: str = "memory",
        compression_enabled: bool = True,
        max_size_mb: int = DEFAULT_MAX_SIZE_MB,
        consolidation_interval: int = DEFAULT_CONSOLIDATION_INTERVAL
    ):
        """
        Initialize DiffMem manager.
        
        Args:
            storage_path: Path to memory storage directory
            compression_enabled: Enable memory compression
            max_size_mb: Maximum memory size in MB
            consolidation_interval: Interval for memory consolidation in seconds
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.compression_enabled = compression_enabled
        self.max_size_mb = max_size_mb
        self.consolidation_interval = consolidation_interval
        
        # Initialize Git repository
        self.repo_path = self.storage_path / "git_storage"
        self.repo_path.mkdir(exist_ok=True)
        self._init_git_repo()
        
        # Memory cache
        self.memories: List[MemoryEntry] = []
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # Thread lock for Git operations
        self._git_lock = threading.Lock()
        
        # Initialize embedding model if available
        self.embedding_model = None
        if EMBEDDINGS_AVAILABLE:
            try:
                self.embedding_model = SentenceTransformer(DEFAULT_EMBEDDING_MODEL)
                logger.info(f"Loaded sentence-transformers embedding model: {DEFAULT_EMBEDDING_MODEL}")
            except Exception as e:
                logger.warning(f"Failed to load embedding model: {e}")
        
        # Start background tasks
        self._consolidation_task = None
        self._sync_task = None
    
    def _init_git_repo(self):
        """Initialize Git repository for memory versioning."""
        try:
            self.repo = Repo(self.repo_path)
            logger.info(f"Using existing Git repository at {self.repo_path}")
        except Exception:
            self.repo = Repo.init(self.repo_path)
            logger.info(f"Initialized new Git repository at {self.repo_path}")
    
    def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding
        """
        if self.embedding_model:
            try:
                embedding = self.embedding_model.encode(text)
                return embedding.tolist()
            except Exception as e:
                logger.error(f"Failed to generate embedding: {e}")
        
        # Fallback: hash-based embedding
        hash_bytes = hashlib.sha256(text.encode()).digest()
        # Convert to normalized float array
        embedding = np.frombuffer(hash_bytes, dtype=np.uint8).astype(float)
        embedding = embedding / np.linalg.norm(embedding)
        return embedding.tolist()
    
    def _compress_content(self, content: str) -> bytes:
        """
        Compress content using zlib.
        
        Args:
            content: Content to compress
            
        Returns:
            Compressed bytes
        """
        return zlib.compress(content.encode('utf-8'), level=9)
    
    def _decompress_content(self, compressed: bytes) -> str:
        """
        Decompress content.
        
        Args:
            compressed: Compressed bytes
            
        Returns:
            Decompressed string
        """
        return zlib.decompress(compressed).decode('utf-8')
    
    async def add_memory(
        self,
        content: str,
        importance: float = 1.0,
        tags: List[str] = None,
        source: str = "unknown"
    ) -> MemoryEntry:
        """
        Add a new memory entry.
        
        Args:
            content: Memory content
            importance: Importance score (0-10)
            tags: Optional tags
            source: Source of the memory
            
        Returns:
            Created memory entry
        """
        # Generate embedding
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            self.executor,
            self._generate_embedding,
            content
        )
        
        # Create memory entry
        memory = MemoryEntry(
            content=content,
            importance=min(max(importance, 0.0), 10.0),
            embedding=embedding,
            tags=tags or [],
            source=source
        )
        
        self.memories.append(memory)
        
        # Save to Git
        await self._save_to_git(memory)
        
        logger.debug(f"Added memory with {len(content)} chars, importance={importance}")
        return memory
    
    async def _save_to_git(self, memory: MemoryEntry):
        """
        Save memory to Git repository.
        
        Args:
            memory: Memory entry to save
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            self._save_to_git_sync,
            memory
        )
    
    def _save_to_git_sync(self, memory: MemoryEntry):
        """Synchronous Git save operation with thread safety."""
        # Acquire lock to prevent concurrent Git operations
        with self._git_lock:
            try:
                # Create filename from timestamp
                filename = f"memory_{int(memory.timestamp * 1000)}.json"
                filepath = self.repo_path / filename
                
                # Prepare data
                data = memory.to_dict()
                if self.compression_enabled and len(memory.content) > 1024:
                    # Compress large content
                    compressed = self._compress_content(memory.content)
                    data['content'] = compressed.hex()
                    data['compressed'] = True
                
                # Write to file
                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=2)
                
                # Git commit
                self.repo.index.add([str(filepath)])
                self.repo.index.commit(
                    f"Add memory: {memory.source} at {datetime.fromtimestamp(memory.timestamp)}"
                )
                
            except Exception as e:
                logger.error(f"Failed to save memory to Git: {e}")
    
    async def retrieve_memories(
        self,
        query: str,
        top_k: int = 5,
        min_importance: float = 0.0
    ) -> List[MemoryEntry]:
        """
        Retrieve memories similar to query.
        
        Args:
            query: Query text
            top_k: Number of memories to retrieve
            min_importance: Minimum importance threshold
            
        Returns:
            List of relevant memory entries
        """
        if not self.memories:
            return []
        
        # Generate query embedding
        loop = asyncio.get_event_loop()
        query_embedding = await loop.run_in_executor(
            self.executor,
            self._generate_embedding,
            query
        )
        
        # Calculate similarity scores
        query_emb = np.array(query_embedding).reshape(1, -1)
        memory_embs = np.array([m.embedding for m in self.memories if m.embedding])
        
        if len(memory_embs) == 0:
            return []
        
        similarities = cosine_similarity(query_emb, memory_embs)[0]
        
        # Filter by importance and get top-k
        scored_memories = []
        for i, memory in enumerate(self.memories):
            if memory.importance >= min_importance:
                score = similarities[i] * (1 + np.log1p(memory.importance))
                scored_memories.append((score, memory))
        
        # Sort by score and return top-k
        scored_memories.sort(reverse=True, key=lambda x: x[0])
        top_memories = [m for _, m in scored_memories[:top_k]]
        
        # Update access statistics
        for memory in top_memories:
            memory.access_count += 1
            memory.last_accessed = time.time()
        
        return top_memories
    
    async def cluster_memories(self, eps: float = DBSCAN_DEFAULT_EPS, min_samples: int = DBSCAN_DEFAULT_MIN_SAMPLES) -> List[List[MemoryEntry]]:
        """
        Cluster similar memories using DBSCAN.
        
        Args:
            eps: Maximum distance between samples
            min_samples: Minimum samples in a cluster
            
        Returns:
            List of memory clusters
        """
        if len(self.memories) < min_samples:
            return [self.memories]
        
        # Get embeddings
        embeddings = np.array([m.embedding for m in self.memories if m.embedding])
        
        if len(embeddings) == 0:
            return [self.memories]
        
        # Perform clustering
        clustering = DBSCAN(eps=eps, min_samples=min_samples, metric='cosine')
        labels = clustering.fit_predict(embeddings)
        
        # Group by cluster
        clusters = {}
        for i, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(self.memories[i])
        
        return list(clusters.values())
    
    async def consolidate_memories(self):
        """Consolidate and compress old memories."""
        if not self.memories:
            return
        
        logger.info("Starting memory consolidation")
        
        # Decay importance over time
        current_time = time.time()
        for memory in self.memories:
            age_days = (current_time - memory.timestamp) / 86400
            decay_factor = np.exp(-age_days / MEMORY_DECAY_HALF_LIFE_DAYS)  # Configurable half-life
            memory.importance *= decay_factor
        
        # Remove low-importance memories
        self.memories = [m for m in self.memories if m.importance > MEMORY_IMPORTANCE_THRESHOLD]
        
        # Cluster and consolidate similar memories
        clusters = await self.cluster_memories()
        logger.info(f"Found {len(clusters)} memory clusters")
        
        logger.info(f"Consolidation complete: {len(self.memories)} memories retained")
    
    async def start_background_tasks(self):
        """Start background consolidation and sync tasks."""
        async def consolidation_loop():
            while True:
                await asyncio.sleep(self.consolidation_interval)
                try:
                    await self.consolidate_memories()
                except Exception as e:
                    logger.error(f"Consolidation failed: {e}")
        
        self._consolidation_task = asyncio.create_task(consolidation_loop())
        logger.info("Started memory consolidation background task")
    
    async def stop_background_tasks(self):
        """Stop background tasks."""
        if self._consolidation_task:
            self._consolidation_task.cancel()
            try:
                await self._consolidation_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped background tasks")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get memory statistics.
        
        Returns:
            Dictionary of statistics
        """
        if not self.memories:
            return {
                "total_memories": 0,
                "total_size_bytes": 0,
                "average_importance": 0,
            }
        
        total_size = sum(len(m.content) for m in self.memories)
        avg_importance = np.mean([m.importance for m in self.memories])
        
        return {
            "total_memories": len(self.memories),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "average_importance": float(avg_importance),
            "compression_enabled": self.compression_enabled,
            "embeddings_available": EMBEDDINGS_AVAILABLE,
        }
