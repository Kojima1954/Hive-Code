#!/bin/bash

# Production Deployment Script for Swarm Network
set -e

echo "================================================"
echo "🐝 Swarm Network - Production Deployment"
echo "================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

# Check for Docker Compose (v2 or v1)
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
    echo -e "${GREEN}✓ Docker Compose v2 detected${NC}"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
    echo -e "${GREEN}✓ Docker Compose v1 detected${NC}"
else
    echo -e "${RED}❌ Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠ .env file not found. Creating from .env.example...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}⚠ Please edit .env file with your configuration${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Environment file found${NC}"

# Pull latest images
echo ""
echo "📦 Pulling latest Docker images..."
$DOCKER_COMPOSE pull

# Build application image
echo ""
echo "🔨 Building application image..."
$DOCKER_COMPOSE build

# Stop existing containers
echo ""
echo "🛑 Stopping existing containers..."
$DOCKER_COMPOSE down

# Start services
echo ""
echo "🚀 Starting services..."
$DOCKER_COMPOSE up -d

# Wait for services to be healthy
echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check health
echo ""
echo "🏥 Checking service health..."
$DOCKER_COMPOSE ps

# Pull Ollama model
echo ""
echo "📥 Pulling Ollama model (this may take a while)..."
$DOCKER_COMPOSE exec -T ollama ollama pull llama2 || echo -e "${YELLOW}⚠ Could not pull Ollama model. Please run: $DOCKER_COMPOSE exec ollama ollama pull llama2${NC}"

echo ""
echo "================================================"
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo "================================================"
echo ""
echo "🌐 Access points:"
echo "   - Web UI:        http://localhost:8000"
echo "   - API Docs:      http://localhost:8000/docs"
echo "   - Prometheus:    http://localhost:9090"
echo "   - Grafana:       http://localhost:3000 (admin/admin)"
echo ""
echo "📊 Useful commands:"
echo "   - View logs:     $DOCKER_COMPOSE logs -f swarm-node"
echo "   - Stop services: $DOCKER_COMPOSE down"
echo "   - Restart:       $DOCKER_COMPOSE restart"
echo ""
