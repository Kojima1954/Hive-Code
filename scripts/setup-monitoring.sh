#!/bin/bash

# Setup Monitoring (Prometheus & Grafana)
set -e

echo "================================================"
echo "📊 Setting up Monitoring Stack"
echo "================================================"

GREEN='\033[0;32m'
NC='\033[0m'

# Create config directories
mkdir -p config/grafana/dashboards
mkdir -p config/grafana/datasources

# Create Grafana datasource configuration
cat > config/grafana/datasources/prometheus.yml << EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
EOF

echo -e "${GREEN}✓ Created Grafana datasource configuration${NC}"

# Create a sample dashboard configuration
cat > config/grafana/dashboards/dashboard.yml << EOF
apiVersion: 1

providers:
  - name: 'Swarm Network'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
EOF

echo -e "${GREEN}✓ Created Grafana dashboard configuration${NC}"

echo ""
echo "================================================"
echo -e "${GREEN}✅ Monitoring setup complete!${NC}"
echo "================================================"
echo ""
echo "🚀 Start monitoring with: docker-compose up -d prometheus grafana"
echo "📊 Access Grafana at: http://localhost:3000 (admin/admin)"
echo ""
