#!/bin/bash
set -e

echo "🚀 Installing LangGraph migration dependencies..."

# Check if python3-venv is available
if ! python3 -m venv --help &>/dev/null; then
    echo "⚠️  python3-venv not found. Installing..."
    sudo apt-get update && sudo apt-get install -y python3-venv python3-full
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install LangGraph dependencies
pip install -r requirements-langgraph.txt

# Create checkpoint directory
mkdir -p data/checkpoints

# Initialize memory collections
echo "📚 Initializing memory collections..."
python3 << 'EOF'
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1] if hasattr(Path(__file__), 'resolve') else Path.cwd()
sys.path.insert(0, str(ROOT_DIR))

try:
    from services.memory.stores.behavior_index import BehaviorIndex
    from services.memory.stores.execution_index import ExecutionIndex
    
    print("  ✓ Behavior index initialized")
    print("  ✓ Execution index initialized")
    
except Exception as e:
    print(f"  ⚠ Memory initialization: {e}")
EOF

echo ""
echo "✅ LangGraph migration setup complete!"
echo ""
echo "Next steps:"
echo "  1. Start services: ./scripts/start_docker_stack.sh"
echo "  2. Run tests: python tests/test_graph_execution.py"
echo "  3. Start Chainlit with LangGraph: ./scripts/start_chainlit.sh"
