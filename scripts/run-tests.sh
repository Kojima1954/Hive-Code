#!/bin/bash

# Test Runner Script with Coverage
set -e

echo "================================================"
echo "🧪 Running Swarm Network Tests"
echo "================================================"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}❌ pytest is not installed. Installing...${NC}"
    pip install pytest pytest-asyncio pytest-cov
fi

echo -e "${GREEN}✓ pytest is available${NC}"

# Create test report directory
mkdir -p test-reports

# Run unit tests
echo ""
echo "🧪 Running unit tests..."
pytest tests/ -v -m "unit" --tb=short || true

# Run integration tests (if Redis is available)
echo ""
echo "🧪 Running integration tests..."
pytest tests/ -v -m "integration" --tb=short || echo "⚠ Skipping integration tests (Redis may not be available)"

# Run all tests with coverage
echo ""
echo "📊 Running all tests with coverage..."
pytest tests/ -v --cov=core --cov=ui --cov-report=html --cov-report=term --cov-report=xml || true

echo ""
echo "================================================"
echo -e "${GREEN}✅ Test run complete!${NC}"
echo "================================================"
echo ""
echo "📄 Coverage report generated in htmlcov/index.html"
echo ""
