# Usage Guide - Conversational Swarm Intelligence Network

## Getting Started

### 1. Installation

#### Quick Start with Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/Kojima1954/Hive-Code.git
cd Hive-Code

# Run the deployment script
./scripts/deploy-production.sh

# Wait for services to start, then access:
# - Web UI: http://localhost:8000
# - Grafana: http://localhost:3000
```

#### Manual Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Start Ollama and pull model
# Visit https://ollama.ai for installation
ollama pull llama2

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run the application
python main.py
```

### 2. Using the Chat Interface

1. **Access the Web UI** at http://localhost:8000
2. **Enter your username** in the login modal
3. **Start chatting!** 
   - Type your message in the input box
   - Press Enter or click Send
   - AI agents will automatically respond

### 3. Working with AI Agents

#### Creating Custom AI Agents

```python
from core.node.node_manager import HumanAINode
import redis.asyncio as redis

# Connect to Redis
redis_client = await redis.from_url("redis://localhost:6379")

# Create a node
node = HumanAINode(
    node_id="my_node",
    redis_client=redis_client
)

# Create a custom AI agent
await node.create_ai_agent(
    agent_id="expert_bot",
    name="Expert Bot",
    model="llama2",
    system_prompt="You are an expert in Python programming. Provide detailed, accurate answers."
)

# Send a message to trigger AI response
await node.process_message(
    sender_id="user_1",
    content="How do I use async/await in Python?"
)
```

#### Using Different Ollama Models

```bash
# Pull different models
ollama pull codellama
ollama pull mistral
ollama pull neural-chat

# Update .env file
OLLAMA_MODEL=codellama
```

### 4. Memory System

#### Storing and Retrieving Memories

```python
from core.memory.diffmem_integration import DiffMemManager

# Create memory manager
memory = DiffMemManager(storage_path="memory")

# Add memories
await memory.add_memory(
    content="Python is a high-level programming language",
    importance=8.0,
    tags=["programming", "python"],
    source="documentation"
)

# Retrieve similar memories
results = await memory.retrieve_memories(
    query="What is Python?",
    top_k=5,
    min_importance=5.0
)

for memory in results:
    print(f"Content: {memory.content}")
    print(f"Importance: {memory.importance}")
```

#### Memory Consolidation

```python
# Start background consolidation
await memory.start_background_tasks()

# Manual consolidation
await memory.consolidate_memories()

# Get memory statistics
stats = memory.get_stats()
print(f"Total memories: {stats['total_memories']}")
print(f"Total size: {stats['total_size_mb']} MB")
```

### 5. Federation and ActivityPub

#### Creating a Federated Actor

```python
from core.federation.fediverse_integration import FediverseConnector

# Create connector
connector = FediverseConnector(
    actor_id="mybot",
    domain="swarm.example.com"
)

# Get actor profile
profile = connector.create_actor_profile()

# Create and send activity
activity = connector.create_activity(
    activity_type="Create",
    content="Hello, Fediverse!",
    to=["https://www.w3.org/ns/activitystreams#Public"]
)

# Send to remote inbox
await connector.send_activity(
    recipient_inbox="https://mastodon.social/inbox",
    activity=activity
)
```

### 6. Security Features

#### Message Encryption

```python
from core.security.encryption import HybridEncryption

# Create encryption instances
sender_enc = HybridEncryption()
recipient_enc = HybridEncryption()

# Encrypt message
message = b"Secret message"
encrypted_data, encrypted_key, nonce = sender_enc.encrypt(
    message,
    recipient_enc.public_key
)

# Decrypt message
decrypted = recipient_enc.decrypt(encrypted_data, encrypted_key, nonce)
```

#### Rate Limiting

Rate limiting is automatically applied via middleware. Configure in .env:

```bash
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60  # seconds
```

### 7. Monitoring and Metrics

#### Accessing Prometheus Metrics

Visit http://localhost:8000/metrics to see raw Prometheus metrics:

```
swarm_messages_total{node_id="main",message_type="text"} 42
swarm_active_participants{node_id="main",participant_type="human"} 5
swarm_websocket_connections 3
```

#### Viewing in Grafana

1. Access Grafana at http://localhost:3000
2. Login with admin/admin
3. Add Prometheus datasource: http://prometheus:9090
4. Create dashboards for:
   - Message throughput
   - Response times
   - Active users
   - Memory usage

#### Example Prometheus Queries

```promql
# Message rate
rate(swarm_messages_total[5m])

# 95th percentile response time
histogram_quantile(0.95, swarm_message_processing_seconds_bucket)

# Active participants by type
swarm_active_participants
```

### 8. API Usage

#### REST API Examples

```bash
# Login and get token
curl -X POST "http://localhost:8000/api/auth/login?username=alice&password=demo"

# Send message (with token)
curl -X POST "http://localhost:8000/api/messages" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello!", "encrypt": false}'

# Get message history
curl "http://localhost:8000/api/messages/history?limit=10"

# Get node statistics
curl "http://localhost:8000/api/node/stats"

# Health check
curl "http://localhost:8000/health"
```

#### WebSocket Example (JavaScript)

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/user_alice');

// Handle connection open
ws.onopen = () => {
    console.log('Connected to swarm network');
    
    // Send a message
    ws.send(JSON.stringify({
        content: "Hello from JavaScript!",
        encrypt: false
    }));
};

// Handle incoming messages
ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    console.log(`${message.sender}: ${message.content}`);
};

// Handle connection close
ws.onclose = () => {
    console.log('Disconnected from swarm network');
};
```

### 9. Kubernetes Deployment

```bash
# Deploy to Kubernetes
kubectl apply -f deployment/kubernetes/redis.yaml
kubectl apply -f deployment/kubernetes/deployment.yaml
kubectl apply -f deployment/kubernetes/grafana.yaml

# Check deployment
kubectl get pods
kubectl get services

# Scale deployment
kubectl scale deployment swarm-network --replicas=5

# View logs
kubectl logs -f deployment/swarm-network

# Access services
kubectl port-forward service/swarm-network-service 8000:80
kubectl port-forward service/grafana-service 3000:3000
```

### 10. Development Workflow

#### Running Tests

```bash
# All tests
./scripts/run-tests.sh

# Specific test file
pytest tests/test_node_manager.py -v

# With coverage report
pytest tests/ --cov=core --cov=ui --cov-report=html
open htmlcov/index.html
```

#### Code Quality

```bash
# Format code
black core/ ui/ tests/

# Type checking
mypy core/ ui/

# Linting
flake8 core/ ui/ tests/
pylint core/ ui/
```

#### Debugging

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Or in .env
LOG_LEVEL=DEBUG
```

### 11. Common Use Cases

#### Multi-User Chat with AI Moderator

```python
# Create moderator agent
await node.create_ai_agent(
    agent_id="moderator",
    name="Moderator Bot",
    system_prompt="You are a helpful moderator. Keep conversations friendly and on-topic."
)

# Add human participants
await node.add_human_participant("user_1", "Alice")
await node.add_human_participant("user_2", "Bob")

# Users chat, moderator participates automatically
```

#### Knowledge Base with Memory

```python
# Build knowledge base
knowledge_items = [
    "Python was created by Guido van Rossum",
    "FastAPI is a modern Python web framework",
    "Redis is an in-memory data store"
]

for item in knowledge_items:
    await memory.add_memory(
        content=item,
        importance=9.0,
        tags=["knowledge", "tech"]
    )

# Query knowledge base
results = await memory.retrieve_memories("Who created Python?", top_k=1)
```

#### Distributed Swarm with Federation

```python
# Node A creates activity
activity = connector_a.create_activity(
    activity_type="Create",
    content="New insight discovered!"
)

# Send to Node B
await connector_a.send_activity(
    recipient_inbox="https://node-b.example.com/inbox",
    activity=activity
)

# Verify blockchain integrity
assert connector_a.verify_blockchain()
```

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   ```bash
   # Check Redis is running
   docker ps | grep redis
   # Or
   redis-cli ping
   ```

2. **Ollama Not Available**
   ```bash
   # Check Ollama status
   ollama list
   # Pull model if missing
   ollama pull llama2
   ```

3. **WebSocket Connection Issues**
   - Check CORS settings in .env
   - Verify firewall allows WebSocket connections
   - Check browser console for errors

4. **High Memory Usage**
   ```bash
   # Check memory stats
   curl http://localhost:8000/api/node/stats
   
   # Trigger consolidation
   # Reduce MEMORY_MAX_SIZE_MB in .env
   ```

## Best Practices

1. **Production Deployment**
   - Use strong JWT_SECRET
   - Enable TLS/SSL
   - Configure specific ALLOWED_ORIGINS
   - Set up monitoring alerts
   - Regular backups of memory storage

2. **Performance**
   - Use Redis connection pooling
   - Enable memory consolidation
   - Monitor Prometheus metrics
   - Scale horizontally with Kubernetes

3. **Security**
   - Rotate JWT secrets regularly
   - Use rate limiting in production
   - Enable encryption for sensitive messages
   - Keep dependencies updated

## Further Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Ollama Models](https://ollama.ai/library)
- [ActivityPub Spec](https://www.w3.org/TR/activitypub/)
- [Prometheus Query Examples](https://prometheus.io/docs/prometheus/latest/querying/examples/)
