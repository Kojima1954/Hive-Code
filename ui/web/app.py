"""FastAPI web application with WebSocket support."""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import jwt
import redis.asyncio as redis
from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect, Depends,
    HTTPException, Request, status
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from core.node.node_manager import HumanAINode, Message
from core.memory.diffmem_integration import DiffMemManager
from core.security.rate_limiting import RateLimitMiddleware
from core.monitoring.health_check import HealthChecker
from core.monitoring.metrics import registry, websocket_connections, increment_counter

logger = logging.getLogger(__name__)


# Pydantic models
class MessageRequest(BaseModel):
    """Request model for sending messages."""
    content: str
    encrypt: bool = False


class MessageResponse(BaseModel):
    """Response model for messages."""
    sender: str
    content: str
    timestamp: float
    message_type: str = "text"


class TokenData(BaseModel):
    """JWT token data."""
    user_id: str
    username: str


# Connection manager for WebSocket
class ConnectionManager:
    """Manages WebSocket connections and message broadcasting."""
    
    def __init__(self, redis_client: redis.Redis, node: HumanAINode):
        """
        Initialize connection manager.
        
        Args:
            redis_client: Redis client for pub/sub
            node: HumanAI node instance
        """
        self.active_connections: Dict[str, WebSocket] = {}
        self.redis = redis_client
        self.node = node
        self.pubsub = redis_client.pubsub()
        self._listener_task = None
    
    async def connect(self, user_id: str, websocket: WebSocket):
        """
        Accept WebSocket connection.
        
        Args:
            user_id: User identifier
            websocket: WebSocket instance
        """
        await websocket.accept()
        self.active_connections[user_id] = websocket
        websocket_connections.set(len(self.active_connections))
        logger.info(f"WebSocket connected: {user_id}")
    
    def disconnect(self, user_id: str):
        """
        Remove WebSocket connection.
        
        Args:
            user_id: User identifier
        """
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            websocket_connections.set(len(self.active_connections))
            logger.info(f"WebSocket disconnected: {user_id}")
    
    async def send_personal_message(self, message: str, user_id: str):
        """
        Send message to specific user.
        
        Args:
            message: Message content
            user_id: Target user ID
        """
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_text(message)
            except Exception as e:
                logger.error(f"Failed to send message to {user_id}: {e}")
                self.disconnect(user_id)
    
    async def broadcast(self, message: str, exclude: str = None):
        """
        Broadcast message to all connected users.
        
        Args:
            message: Message content
            exclude: Optional user ID to exclude from broadcast
        """
        disconnected = []
        for user_id, connection in self.active_connections.items():
            if user_id != exclude:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Failed to broadcast to {user_id}: {e}")
                    disconnected.append(user_id)
        
        # Clean up disconnected users
        for user_id in disconnected:
            self.disconnect(user_id)
    
    async def start_redis_listener(self):
        """Start Redis pub/sub listener for cross-process messaging."""
        async def listen():
            await self.pubsub.subscribe(f"node:{self.node.node_id}")
            logger.info(f"Started Redis listener for node:{self.node.node_id}")
            
            async for message in self.pubsub.listen():
                if message['type'] == 'message':
                    try:
                        # Broadcast to all WebSocket connections
                        await self.broadcast(message['data'].decode('utf-8'))
                    except Exception as e:
                        logger.error(f"Failed to broadcast Redis message: {e}")
        
        self._listener_task = asyncio.create_task(listen())
    
    async def stop_redis_listener(self):
        """Stop Redis pub/sub listener."""
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        
        await self.pubsub.unsubscribe()


# Create FastAPI app
def create_app(
    redis_url: str = "redis://localhost:6379",
    ollama_host: str = "http://localhost:11434",
    jwt_secret: str = "change-this",
    allowed_origins: List[str] = ["*"]
) -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Args:
        redis_url: Redis connection URL
        ollama_host: Ollama server URL
        jwt_secret: JWT secret key
        allowed_origins: CORS allowed origins
        
    Returns:
        Configured FastAPI app
    """
    # Validate JWT secret strength
    if jwt_secret in ["change-this", "change-this-secret-key", "test", "demo"]:
        logger.warning(
            "⚠️  SECURITY WARNING: Using weak or default JWT secret! "
            "This is INSECURE for production. Set a strong JWT_SECRET environment variable."
        )
    
    if len(jwt_secret) < 32:
        logger.warning(
            f"⚠️  SECURITY WARNING: JWT secret is only {len(jwt_secret)} characters. "
            "Recommend at least 32 characters for production use."
        )
    
    # Validate CORS configuration
    if "*" in allowed_origins:
        logger.warning(
            "⚠️  SECURITY WARNING: CORS allows all origins (*). "
            "This is INSECURE for production. Set specific ALLOWED_ORIGINS."
        )
    
    app = FastAPI(
        title="Conversational Swarm Intelligence Network",
        description="Production-ready swarm intelligence network with AI agents",
        version="1.0.0"
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # State variables
    app.state.redis_client = None
    app.state.node = None
    app.state.memory_manager = None
    app.state.connection_manager = None
    app.state.health_checker = None
    app.state.jwt_secret = jwt_secret
    app.state.ollama_host = ollama_host
    app.state.redis_url = redis_url
    
    @app.on_event("startup")
    async def startup_event():
        """Initialize services on startup."""
        logger.info("Starting Swarm Network application...")
        
        # Connect to Redis
        try:
            app.state.redis_client = await redis.from_url(
                app.state.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await app.state.redis_client.ping()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
        
        # Initialize memory manager
        app.state.memory_manager = DiffMemManager()
        await app.state.memory_manager.start_background_tasks()
        
        # Initialize node
        app.state.node = HumanAINode(
            node_id="main",
            redis_client=app.state.redis_client,
            memory_manager=app.state.memory_manager
        )
        
        # Create default AI agent
        await app.state.node.create_ai_agent(
            agent_id="assistant",
            name="SwarmBot",
            model="llama2",
            ollama_host=app.state.ollama_host,
            system_prompt="You are SwarmBot, a helpful AI assistant in a swarm intelligence network. Provide concise, helpful responses."
        )
        
        # Initialize connection manager
        app.state.connection_manager = ConnectionManager(
            app.state.redis_client,
            app.state.node
        )
        await app.state.connection_manager.start_redis_listener()
        
        # Initialize health checker
        app.state.health_checker = HealthChecker(app.state.redis_client)
        
        # Add rate limiting middleware
        app.add_middleware(RateLimitMiddleware, redis_client=app.state.redis_client)
        
        logger.info("Swarm Network application started successfully")
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown."""
        logger.info("Shutting down Swarm Network application...")
        
        if app.state.connection_manager:
            await app.state.connection_manager.stop_redis_listener()
        
        if app.state.node:
            await app.state.node.stop_listener()
        
        if app.state.memory_manager:
            await app.state.memory_manager.stop_background_tasks()
        
        if app.state.redis_client:
            await app.state.redis_client.close()
        
        logger.info("Shutdown complete")
    
    # JWT authentication
    def create_token(user_id: str, username: str) -> str:
        """Create JWT token."""
        payload = {
            "user_id": user_id,
            "username": username,
            "exp": datetime.now(timezone.utc) + timedelta(hours=24)
        }
        return jwt.encode(payload, app.state.jwt_secret, algorithm="HS256")
    
    def verify_token(token: str) -> TokenData:
        """Verify JWT token."""
        try:
            payload = jwt.decode(token, app.state.jwt_secret, algorithms=["HS256"])
            return TokenData(
                user_id=payload["user_id"],
                username=payload["username"]
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    # Routes
    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve main page."""
        try:
            with open("ui/web/static/index.html", "r") as f:
                return f.read()
        except FileNotFoundError:
            return "<h1>Conversational Swarm Intelligence Network</h1><p>UI not found. Please check installation.</p>"
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        if app.state.health_checker:
            health_status = await app.state.health_checker.get_health_status()
            status_code = 200 if health_status["status"] in ["healthy", "degraded"] else 503
            return JSONResponse(content=health_status, status_code=status_code)
        return {"status": "unknown"}
    
    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint."""
        from fastapi.responses import Response
        return Response(
            content=generate_latest(registry),
            media_type=CONTENT_TYPE_LATEST
        )
    
    @app.post("/api/auth/login")
    async def login(username: str, password: str = "demo"):
        """
        Login endpoint (DEMO ONLY - accepts any credentials).
        
        ⚠️  WARNING: This is a simplified demo authentication.
        In production, you MUST:
        - Verify credentials against a real user database
        - Use proper password hashing (bcrypt, argon2, etc.)
        - Implement rate limiting on login attempts
        - Add CAPTCHA for brute force protection
        - Log authentication attempts
        """
        # In production, verify against a real user database
        user_id = f"user_{username}"
        token = create_token(user_id, username)
        
        # Add user to node
        await app.state.node.add_human_participant(user_id, username)
        
        logger.info(f"User logged in: {username} (DEMO MODE)")
        
        return {
            "token": token,
            "user_id": user_id,
            "username": username
        }
    
    @app.post("/api/messages", response_model=MessageResponse)
    async def send_message(
        message_req: MessageRequest,
        request: Request
    ):
        """Send a message."""
        # Extract user from token (simplified)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                token_data = verify_token(token)
                user_id = token_data.user_id
            except HTTPException:
                user_id = "anonymous"
        else:
            user_id = "anonymous"
        
        # Process message
        message = await app.state.node.process_message(
            sender_id=user_id,
            content=message_req.content,
            encrypt=message_req.encrypt
        )
        
        return MessageResponse(
            sender=message.sender,
            content=message.content,
            timestamp=message.timestamp,
            message_type=message.message_type
        )
    
    @app.get("/api/messages/history")
    async def get_history(limit: int = 50):
        """Get message history."""
        messages = await app.state.node.get_conversation_history(limit)
        return [
            MessageResponse(
                sender=msg.sender,
                content=msg.content,
                timestamp=msg.timestamp,
                message_type=msg.message_type
            )
            for msg in messages
        ]
    
    @app.get("/api/node/summary")
    async def get_node_summary():
        """Get node summary."""
        summary = await app.state.node.generate_node_summary()
        return {"summary": summary}
    
    @app.get("/api/node/stats")
    async def get_node_stats():
        """Get node statistics."""
        return app.state.node.get_stats()
    
    @app.websocket("/ws/{user_id}")
    async def websocket_endpoint(websocket: WebSocket, user_id: str):
        """WebSocket endpoint for real-time chat."""
        await app.state.connection_manager.connect(user_id, websocket)
        
        # Add user to node
        await app.state.node.add_human_participant(user_id, user_id)
        
        try:
            while True:
                # Receive message
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Process message
                message = await app.state.node.process_message(
                    sender_id=user_id,
                    content=message_data.get("content", ""),
                    encrypt=message_data.get("encrypt", False)
                )
                
                # Broadcast to others
                response = json.dumps({
                    "sender": message.sender,
                    "content": message.content,
                    "timestamp": message.timestamp,
                    "message_type": message.message_type
                })
                await app.state.connection_manager.broadcast(response)
                
        except WebSocketDisconnect:
            app.state.connection_manager.disconnect(user_id)
            logger.info(f"User {user_id} disconnected")
        except Exception as e:
            logger.error(f"WebSocket error for {user_id}: {e}")
            app.state.connection_manager.disconnect(user_id)
    
    return app


# Create default app instance
app = create_app(
    redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
    ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
    jwt_secret=os.getenv("JWT_SECRET", "change-this-secret-key"),
    allowed_origins=os.getenv("ALLOWED_ORIGINS", "*").split(",")
)
