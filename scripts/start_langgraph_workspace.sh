#!/bin/bash
set -e

echo "🚀 RAY → God Mode Agent (LangGraph) Quick Start"
echo "================================================"
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
./scripts/install_langgraph.sh

# Start Docker services
echo ""
echo "🐳 Starting Docker services..."
./scripts/start_docker_stack.sh

# Wait for services
echo ""
echo "⏳ Waiting for services to be ready..."
sleep 5

# Run tests
echo ""
echo "🧪 Running tests..."
python tests/test_memory_promotion.py
python tests/test_verifier_coverage.py

# Start Chainlit
echo ""
echo "✅ Setup complete!"
echo ""
echo "Starting Chainlit UI..."
echo "Access at: http://localhost:8001"
echo ""
echo "Commands:"
echo "  /langgraph - Use LangGraph mode (default)"
echo "  /crewai    - Use CrewAI fallback mode"
echo ""

chainlit run apps/ui-chainlit/app.py -w --port 8001
