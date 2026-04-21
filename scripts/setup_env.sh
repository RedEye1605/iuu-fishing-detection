#!/usr/bin/env bash
# Environment setup script for IUU fishing detection
# Run from project root: ./scripts/setup_env.sh

set -e

echo "🚀 Setting up IUU Fishing Detection environment..."
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✓ Python version: $PYTHON_VERSION"

if (( $(echo "$PYTHON_VERSION < 3.12" | bc -l) )); then
    echo "❌ Python 3.12+ is required. Your version is $PYTHON_VERSION"
    exit 1
fi

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed"
    echo "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "✓ uv is installed"

# Create virtual environment
echo ""
echo "📦 Creating virtual environment..."
uv venv .venv --python 3.12

echo "✓ Virtual environment created"

# Activate and install dependencies
echo ""
echo "🔧 Installing dependencies..."
source .venv/bin/activate
uv pip install -e .

echo "✓ Dependencies installed"

# Setup environment file if not exists
if [ ! -f .env ]; then
    echo ""
    echo "📝 Creating .env from template..."
    cp .env.example .env
    echo "✓ .env created (edit with your API tokens)"
else
    echo "✓ .env already exists"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env and add your API tokens"
echo "  2. Run SAR data: python scripts/pull_sar_data.py"
echo "  3. Run tests: pytest"
echo "  4. Explore data: cd notebooks && jupyter notebook"
