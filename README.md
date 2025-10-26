# 🐝 Conversational Swarm Intelligence Network

A production-ready distributed AI conversation system that combines human participants with AI agents in a swarm intelligence network. Features real-time communication, distributed memory, ActivityPub federation, and enterprise-grade security.

## ✨ Features

### Core Capabilities
- **🤖 AI Agent Integration**: Seamlessly integrate Ollama-powered LLM agents into conversations
- **👥 Human-AI Collaboration**: Multi-participant conversations mixing humans and AI agents
- **🧠 Distributed Memory**: Git-based memory versioning with embeddings and intelligent retrieval
- **🌐 Federation Support**: ActivityPub protocol integration with blockchain verification
- **🔐 Enterprise Security**: Hybrid RSA+AES-GCM encryption, rate limiting, DDoS protection
- **📊 Comprehensive Monitoring**: Prometheus metrics, structured logging, health checks
- **⚡ Real-time Communication**: WebSocket-based chat with Redis pub/sub
- **📈 Auto-scaling**: Kubernetes support with HPA and StatefulSets
- **🎨 Modern UI**: WhatsApp-style responsive chat interface

### Technical Features
- **Async/Await Architecture**: Non-blocking I/O throughout
- **Memory Intelligence**: Embeddings, clustering, importance scoring, automatic consolidation
- **Rate Limiting**: Redis-based sliding window with IP banning
- **TLS/SSL Support**: Self-signed certificate generation, production-ready encryption
- **Health Monitoring**: System metrics (CPU, memory, disk), service health checks
- **Docker & Kubernetes**: Full containerization with production-ready deployments
- **Comprehensive Testing**: Unit and integration tests with pytest

## 🚀 Quick Start

### Windows

1. **Prerequisites**
   ```powershell
   # Requires Python 3.11+, Docker Desktop, and Ollama
   choco install python docker-desktop
   ```

2. **Setup Development Environment**
   ```powershell
   .\scripts\setup-dev.ps1
   ```

3. **Start Infrastructure**
   ```powershell
   docker run -d -p 6379:6379 redis
   # Install and start Ollama from https://ollama.ai
   ollama pull llama2
   ```

4. **Run Application**
   ```powershell
   python main.py
   ```

### Linux/macOS

1. **Prerequisites**
   ```bash
   # Requires Python 3.11+, Docker, and Ollama
   sudo apt update && sudo apt install python3.11 python3-pip docker.io
   ```

2. **Setup Development Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   ```

3. **Start Infrastructure**
   ```bash
   docker run -d -p 6379:6379 redis
   # Install Ollama from https://ollama.ai
   ollama pull llama2
   ```

4. **Run Application**
   ```bash
   python main.py
   ```

### Docker Compose (Recommended)

```bash
# Start all services
./scripts/deploy-production.sh

# Or manually
docker-compose up -d

# Pull Ollama model
docker-compose exec ollama ollama pull llama2
```

Access the application:
- **Web UI**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)

## 📁 Project Structure

```
conversational-swarm-network/
├── core/                           # Core business logic
│   ├── node/                       # Node and participant management
│   │   └── node_manager.py         # HumanAINode, AI agents, message routing
│   ├── federation/                 # Federation and blockchain
│   │   └── fediverse_integration.py # ActivityPub, blockchain verification
│   ├── memory/                     # Distributed memory
│   │   └── diffmem_integration.py  # Git-based memory with embeddings
│   ├── security/                   # Security modules
│   │   ├── encryption.py           # Hybrid RSA+AES-GCM encryption
│   │   ├── rate_limiting.py        # Redis-based rate limiting
│   │   └── tls_config.py           # TLS/SSL certificate management
│   └── monitoring/                 # Monitoring and observability
│       ├── metrics.py              # Prometheus metrics
│       ├── logging_config.py       # Structured JSON logging
│       └── health_check.py         # Health checks and system metrics
├── ui/                             # User interface
│   └── web/                        # Web application
│       ├── app.py                  # FastAPI app with WebSocket
│       └── static/
│           └── index.html          # WhatsApp-style chat UI
├── deployment/                     # Deployment configurations
│   ├── docker/
│   │   └── Dockerfile              # Production Docker image
│   └── kubernetes/
│       ├── deployment.yaml         # K8s deployment with HPA
│       ├── redis.yaml              # Redis StatefulSet
│       └── grafana.yaml            # Grafana deployment
├── config/                         # Configuration files
│   ├── prometheus.yml              # Prometheus scrape configs
│   └── grafana/                    # Grafana dashboards and datasources
├── tests/                          # Test suite
│   ├── test_node_manager.py        # Node and agent tests
│   ├── test_diffmem.py             # Memory system tests
│   ├── test_federation.py          # Security and federation tests
│   ├── test_api.py                 # API endpoint tests
│   └── conftest.py                 # Pytest fixtures
├── scripts/                        # Utility scripts
│   ├── deploy-production.sh        # Production deployment
│   ├── run-tests.sh                # Test runner with coverage
│   ├── setup-monitoring.sh         # Monitoring stack setup
│   └── setup-dev.ps1               # Windows dev environment setup
├── main.py                         # Application entry point
├── requirements.txt                # Python dependencies
├── docker-compose.yml              # Multi-service orchestration
├── pytest.ini                      # Pytest configuration
└── .env.example                    # Environment variables template
```

## ⚙️ Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Application
DOMAIN=localhost
PORT=8000
LOG_LEVEL=INFO

# Security
JWT_SECRET=your-secret-key-here
JWT_ALGORITHM=HS256

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_URL=redis://localhost:6379

# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama2

# CORS
ALLOWED_ORIGINS=*

# Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# TLS (optional)
TLS_ENABLED=false
TLS_CERT_PATH=certs/server.crt
TLS_KEY_PATH=certs/server.key
```

## 🧪 Development

### Running Tests

```bash
# All tests
./scripts/run-tests.sh

# Specific test file
pytest tests/test_node_manager.py -v

# With coverage
pytest tests/ --cov=core --cov=ui --cov-report=html
```

### Code Style

```bash
# Format code
black core/ ui/ tests/

# Lint
flake8 core/ ui/ tests/
pylint core/ ui/
```

## 🐳 Docker Deployment

### Build and Run

```bash
# Build image
docker build -t swarm-network -f deployment/docker/Dockerfile .

# Run container
docker run -d \
  -p 8000:8000 \
  -e REDIS_URL=redis://redis:6379 \
  -e OLLAMA_HOST=http://ollama:11434 \
  swarm-network
```

### Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f swarm-node

# Stop services
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

## ☸️ Kubernetes Deployment

### Deploy to Kubernetes

```bash
# Create namespace
kubectl create namespace swarm-network

# Deploy Redis
kubectl apply -f deployment/kubernetes/redis.yaml

# Deploy application
kubectl apply -f deployment/kubernetes/deployment.yaml

# Deploy monitoring
kubectl apply -f deployment/kubernetes/grafana.yaml

# Check status
kubectl get pods -n swarm-network
kubectl get services -n swarm-network
```

### Scale Deployment

```bash
# Manual scaling
kubectl scale deployment swarm-network --replicas=5

# HPA is configured for auto-scaling based on CPU/memory
```

## 📊 Monitoring

### Prometheus Metrics

Available at `/metrics`:
- `swarm_messages_total`: Total messages processed
- `swarm_message_processing_seconds`: Message processing time
- `swarm_active_participants`: Active participants by type
- `swarm_memory_size_bytes`: Memory storage size
- `swarm_errors_total`: Error counter
- `swarm_websocket_connections`: Active WebSocket connections

### Grafana Dashboards

Access Grafana at `http://localhost:3000` (admin/admin):
1. Add Prometheus datasource: http://prometheus:9090
2. Create dashboards for:
   - Message throughput
   - Response times
   - Memory usage
   - Error rates
   - System resources

## 🔐 Security

### Encryption

- **Message Encryption**: Hybrid RSA-4096 + AES-256-GCM
- **TLS/SSL**: Self-signed or custom certificates
- **JWT Authentication**: Secure token-based auth
- **Rate Limiting**: Redis-based sliding window

### Best Practices

1. Change `JWT_SECRET` in production
2. Use strong passwords for Grafana
3. Enable TLS for production deployments
4. Configure CORS for specific origins
5. Set up firewall rules
6. Regular security updates

## 🤝 API Reference

### REST Endpoints

- `GET /`: Web UI
- `GET /health`: Health check
- `GET /metrics`: Prometheus metrics
- `POST /api/auth/login`: User authentication
- `POST /api/messages`: Send message
- `GET /api/messages/history`: Get message history
- `GET /api/node/summary`: Node summary
- `GET /api/node/stats`: Node statistics

### WebSocket

Connect to `/ws/{user_id}` for real-time chat:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/user_123');

ws.onopen = () => {
    ws.send(JSON.stringify({
        content: "Hello, Swarm!",
        encrypt: false
    }));
};

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    console.log(message);
};
```

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Ollama**: Local LLM inference
- **FastAPI**: Modern Python web framework
- **Redis**: In-memory data structure store
- **Prometheus & Grafana**: Monitoring and visualization
- **ActivityPub**: Decentralized social networking protocol

## 📧 Support

For issues, questions, or contributions, please open an issue on GitHub.

---

**Built with ❤️ for the Swarm Intelligence Community**
