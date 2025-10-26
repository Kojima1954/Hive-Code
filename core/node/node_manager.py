"""Node manager for HumanAI conversation with Ollama agents."""

import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod

import redis.asyncio as redis
from cryptography.fernet import Fernet
import ollama

from core.memory.diffmem_integration import DiffMemManager
from core.monitoring.metrics import (
    message_counter, message_processing_time,
    active_participants, increment_counter, track_time
)

logger = logging.getLogger(__name__)

# Constants
MAX_MESSAGE_QUEUE_SIZE = 1000
MAX_CONTEXT_MESSAGES = 10
AI_AGENT_CONTEXT_WINDOW = 5  # Number of recent messages to include in AI context


class ParticipantType(Enum):
    """Type of participant in the conversation."""
    HUMAN = "human"
    AI_AGENT = "ai_agent"


@dataclass
class Message:
    """Represents a message in the conversation."""
    
    sender: str
    content: str
    timestamp: float = field(default_factory=time.time)
    message_type: str = "text"
    metadata: Dict[str, Any] = field(default_factory=dict)
    encrypted: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary."""
        return cls(**data)


@dataclass
class NodeParticipant:
    """Represents a participant in the node."""
    
    id: str
    name: str
    type: ParticipantType
    public_key: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    joined_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['type'] = self.type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NodeParticipant':
        """Create from dictionary."""
        data = data.copy()
        if 'type' in data and isinstance(data['type'], str):
            data['type'] = ParticipantType(data['type'])
        return cls(**data)


class BaseAgent(ABC):
    """Abstract base class for AI agents."""
    
    def __init__(self, agent_id: str, name: str):
        """
        Initialize base agent.
        
        Args:
            agent_id: Unique agent identifier
            name: Agent display name
        """
        self.agent_id = agent_id
        self.name = name
        self.conversation_history: List[Dict[str, str]] = []
    
    @abstractmethod
    async def generate_response(self, message: str, context: List[Message] = None) -> str:
        """
        Generate response to a message.
        
        Args:
            message: Input message
            context: Optional conversation context
            
        Returns:
            Generated response
        """
        pass
    
    def add_to_history(self, role: str, content: str):
        """Add message to conversation history."""
        self.conversation_history.append({
            "role": role,
            "content": content
        })


class OllamaAgent(BaseAgent):
    """AI agent using Ollama for LLM inference."""
    
    def __init__(
        self,
        agent_id: str,
        name: str,
        model: str = "llama2",
        ollama_host: str = "http://localhost:11434",
        system_prompt: str = None
    ):
        """
        Initialize Ollama agent.
        
        Args:
            agent_id: Unique agent identifier
            name: Agent display name
            model: Ollama model name
            ollama_host: Ollama server URL
            system_prompt: Optional system prompt
        """
        super().__init__(agent_id, name)
        self.model = model
        self.ollama_host = ollama_host
        self.system_prompt = system_prompt or f"You are {name}, a helpful AI assistant in a swarm intelligence network."
        
        # Initialize Ollama client
        try:
            self.client = ollama.Client(host=ollama_host)
            logger.info(f"Initialized Ollama agent '{name}' with model '{model}'")
        except Exception as e:
            logger.error(f"Failed to initialize Ollama client: {e}")
            self.client = None
    
    async def generate_response(self, message: str, context: List[Message] = None) -> str:
        """
        Generate response using Ollama.
        
        Args:
            message: Input message
            context: Optional conversation context
            
        Returns:
            Generated response
        """
        if not self.client:
            return "Sorry, I'm currently unavailable. Ollama service is not accessible."
        
        try:
            # Build conversation context
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Add recent context (use constant for window size)
            if context:
                for ctx_msg in context[-AI_AGENT_CONTEXT_WINDOW:]:  # Last N messages
                    role = "user" if ctx_msg.sender != self.agent_id else "assistant"
                    messages.append({"role": role, "content": ctx_msg.content})
            
            # Add current message
            messages.append({"role": "user", "content": message})
            
            # Generate response (run in executor to avoid blocking)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat(
                    model=self.model,
                    messages=messages
                )
            )
            
            # Extract response content
            if response and 'message' in response:
                content = response['message']['content']
                self.add_to_history("user", message)
                self.add_to_history("assistant", content)
                return content
            else:
                return "I couldn't generate a response. Please try again."
                
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            return f"Sorry, I encountered an error: {str(e)}"


class HumanAINode:
    """
    Node managing human and AI participants with conversation capabilities.
    """
    
    def __init__(
        self,
        node_id: str,
        redis_client: redis.Redis,
        memory_manager: DiffMemManager = None,
        encryption_key: bytes = None
    ):
        """
        Initialize HumanAI node.
        
        Args:
            node_id: Unique node identifier
            redis_client: Redis client for pub/sub
            memory_manager: Optional DiffMem manager
            encryption_key: Optional Fernet encryption key
        """
        self.node_id = node_id
        self.redis = redis_client
        self.memory_manager = memory_manager or DiffMemManager()
        
        # Initialize encryption
        self.encryption_key = encryption_key or Fernet.generate_key()
        self.cipher = Fernet(self.encryption_key)
        
        # Participants
        self.participants: Dict[str, NodeParticipant] = {}
        self.agents: Dict[str, BaseAgent] = {}
        
        # Message queue (use deque for O(1) operations)
        self.message_queue: deque = deque(maxlen=MAX_MESSAGE_QUEUE_SIZE)  # Auto-removes old messages
        self.max_queue_size = MAX_MESSAGE_QUEUE_SIZE  # Kept for backwards compatibility
        
        # Redis pub/sub
        self.pubsub = self.redis.pubsub()
        self.channel = f"node:{node_id}"
        
        # Background tasks
        self._listener_task = None
        
        logger.info(f"Initialized HumanAI node: {node_id}")
    
    def encrypt_message(self, content: str) -> str:
        """
        Encrypt message content.
        
        Args:
            content: Message content
            
        Returns:
            Encrypted content (base64)
        """
        encrypted = self.cipher.encrypt(content.encode('utf-8'))
        return encrypted.decode('utf-8')
    
    def decrypt_message(self, encrypted_content: str) -> str:
        """
        Decrypt message content.
        
        Args:
            encrypted_content: Encrypted content (base64)
            
        Returns:
            Decrypted content
        """
        decrypted = self.cipher.decrypt(encrypted_content.encode('utf-8'))
        return decrypted.decode('utf-8')
    
    async def add_human_participant(self, user_id: str, name: str, public_key: str = None) -> NodeParticipant:
        """
        Add a human participant to the node.
        
        Args:
            user_id: Unique user identifier
            name: User display name
            public_key: Optional public key for encryption
            
        Returns:
            Created participant
        """
        participant = NodeParticipant(
            id=user_id,
            name=name,
            type=ParticipantType.HUMAN,
            public_key=public_key
        )
        
        self.participants[user_id] = participant
        
        # Update metrics
        active_participants.labels(
            node_id=self.node_id,
            participant_type=ParticipantType.HUMAN.value
        ).set(sum(1 for p in self.participants.values() if p.type == ParticipantType.HUMAN))
        
        logger.info(f"Added human participant: {name} ({user_id})")
        return participant
    
    async def create_ai_agent(
        self,
        agent_id: str,
        name: str,
        model: str = "llama2",
        ollama_host: str = "http://localhost:11434",
        system_prompt: str = None
    ) -> OllamaAgent:
        """
        Create an AI agent in the node.
        
        Args:
            agent_id: Unique agent identifier
            name: Agent display name
            model: Ollama model name
            ollama_host: Ollama server URL
            system_prompt: Optional system prompt
            
        Returns:
            Created agent
        """
        agent = OllamaAgent(
            agent_id=agent_id,
            name=name,
            model=model,
            ollama_host=ollama_host,
            system_prompt=system_prompt
        )
        
        self.agents[agent_id] = agent
        
        # Add as participant
        participant = NodeParticipant(
            id=agent_id,
            name=name,
            type=ParticipantType.AI_AGENT,
            metadata={"model": model}
        )
        self.participants[agent_id] = participant
        
        # Update metrics
        active_participants.labels(
            node_id=self.node_id,
            participant_type=ParticipantType.AI_AGENT.value
        ).set(sum(1 for p in self.participants.values() if p.type == ParticipantType.AI_AGENT))
        
        logger.info(f"Created AI agent: {name} ({agent_id}) with model {model}")
        return agent
    
    @track_time(message_processing_time, {"node_id": "default"})
    async def process_message(
        self,
        sender_id: str,
        content: str,
        encrypt: bool = False,
        store_in_memory: bool = True,
        trigger_agents: bool = True
    ) -> Message:
        """
        Process and route a message.
        
        Args:
            sender_id: ID of message sender
            content: Message content
            encrypt: Whether to encrypt the message
            store_in_memory: Whether to store in memory
            trigger_agents: Whether to trigger AI agent responses (prevents infinite recursion)
            
        Returns:
            Processed message
        """
        # Create message
        message_content = content
        if encrypt:
            message_content = self.encrypt_message(content)
        
        message = Message(
            sender=sender_id,
            content=message_content,
            encrypted=encrypt
        )
        
        # Add to queue (deque automatically handles max size)
        self.message_queue.append(message)
        
        # Store in memory
        if store_in_memory:
            await self.memory_manager.add_memory(
                content=content,
                importance=1.0,
                tags=["message", f"sender:{sender_id}"],
                source=sender_id
            )
        
        # Publish to Redis
        await self.redis.publish(
            self.channel,
            json.dumps(message.to_dict())
        )
        
        # Update metrics
        increment_counter(
            message_counter,
            {"node_id": self.node_id, "message_type": "text"}
        )
        
        # Process with AI agents if applicable (only for non-agent messages to prevent infinite loops)
        if trigger_agents:
            await self._process_with_agents(message)
        
        logger.debug(f"Processed message from {sender_id}")
        return message
    
    async def _process_with_agents(self, message: Message):
        """
        Process message with AI agents and generate responses.
        
        Args:
            message: Message to process
        """
        # Decrypt if needed
        content = message.content
        if message.encrypted:
            try:
                content = self.decrypt_message(content)
            except Exception as e:
                logger.error(f"Failed to decrypt message: {e}")
                return
        
        # Check if any agents should respond
        for agent_id, agent in self.agents.items():
            # Skip if message is from this agent
            if message.sender == agent_id:
                continue
            
            # Generate response
            try:
                response_content = await agent.generate_response(
                    content,
                    context=list(self.message_queue)[-MAX_CONTEXT_MESSAGES:]  # Last N messages as context
                )
                
                # Send agent response (with trigger_agents=False to prevent infinite recursion)
                await self.process_message(
                    sender_id=agent_id,
                    content=response_content,
                    encrypt=message.encrypted,
                    store_in_memory=True,
                    trigger_agents=False  # Critical: prevent agents from responding to each other
                )
                
            except Exception as e:
                logger.error(f"Agent {agent_id} failed to generate response: {e}")
    
    async def start_listener(self):
        """Start Redis pub/sub listener."""
        async def listen():
            await self.pubsub.subscribe(self.channel)
            logger.info(f"Subscribed to channel: {self.channel}")
            
            async for message in self.pubsub.listen():
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        msg = Message.from_dict(data)
                        logger.debug(f"Received message: {msg.sender}")
                    except Exception as e:
                        logger.error(f"Failed to process received message: {e}")
        
        self._listener_task = asyncio.create_task(listen())
        logger.info("Started message listener")
    
    async def stop_listener(self):
        """Stop Redis pub/sub listener."""
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        
        await self.pubsub.unsubscribe(self.channel)
        logger.info("Stopped message listener")
    
    async def get_conversation_history(self, limit: int = 50) -> List[Message]:
        """
        Get recent conversation history.
        
        Args:
            limit: Maximum number of messages to return
            
        Returns:
            List of recent messages
        """
        # Convert deque to list and get last N messages
        messages = list(self.message_queue)
        return messages[-limit:] if len(messages) > limit else messages
    
    async def generate_node_summary(self) -> str:
        """
        Generate a summary of the node's current state.
        
        Returns:
            Node summary
        """
        summary_parts = [
            f"Node ID: {self.node_id}",
            f"Total Participants: {len(self.participants)}",
            f"Human Participants: {sum(1 for p in self.participants.values() if p.type == ParticipantType.HUMAN)}",
            f"AI Agents: {sum(1 for p in self.participants.values() if p.type == ParticipantType.AI_AGENT)}",
            f"Messages in Queue: {len(self.message_queue)}",
        ]
        
        # Add memory stats
        mem_stats = self.memory_manager.get_stats()
        summary_parts.append(f"Total Memories: {mem_stats['total_memories']}")
        summary_parts.append(f"Memory Size: {mem_stats.get('total_size_mb', 0):.2f} MB")
        
        return "\n".join(summary_parts)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get node statistics.
        
        Returns:
            Dictionary of node statistics
        """
        return {
            "node_id": self.node_id,
            "participants": len(self.participants),
            "human_participants": sum(1 for p in self.participants.values() if p.type == ParticipantType.HUMAN),
            "ai_agents": sum(1 for p in self.participants.values() if p.type == ParticipantType.AI_AGENT),
            "messages_in_queue": len(self.message_queue),
            "memory_stats": self.memory_manager.get_stats(),
        }
