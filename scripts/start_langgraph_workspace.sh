#!/bin/bash
set -e

echo "RAY - God Mode Agent (LangGraph) Quick Start"
echo "============================================="
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
./scripts/install_langgraph.sh

# Start Docker services
echo ""
echo "Starting Docker services..."
./scripts/start_docker_stack.sh

# Wait for services
echo ""
echo "Waiting for services to be ready..."
sleep 5

# Run tests
echo ""
echo "Running tests..."
python tests/test_memory_promotion.py
python tests/test_verifier_coverage.py

# Start the app
echo ""
echo "Setup complete!"
echo ""
echo "Starting RAY App..."
echo "  API:  http://localhost:8002"
echo "  Web:  http://localhost:5173"
echo ""

./scripts/start_app.sh
