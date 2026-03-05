#!/bin/bash
# DEPLOY.sh - One-command trading bot deployment
# Usage: ./DEPLOY.sh

set -e

echo "=========================================="
echo "🚀 CRYPTO GOD JOHN - TRADING BOT DEPLOY"
echo "=========================================="

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found"
    exit 1
fi

echo "✅ Python found"

# Check dependencies
echo ""
echo "📦 Installing dependencies..."
pip install -q requests cryptography python-dotenv 2>/dev/null || pip3 install -q requests cryptography python-dotenv

# Check .env
echo ""
echo "🔑 Checking credentials..."
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "Create one with:"
    echo "  COINBASE_API_KEY_NAME=your_key"
    echo "  COINBASE_API_PRIVATE_KEY=your_secret"
    echo "  PAPER_MODE=true"
    exit 1
fi

echo "✅ .env found"

# Test connection
echo ""
echo "📡 Testing Coinbase connection..."
python3 -c "
from dotenv import load_dotenv
load_dotenv()
from coinbase_legacy import CoinbaseLegacyClient
client = CoinbaseLegacyClient()
btc = client.get_product_price('BTC-USD')
print(f'✅ Connected - BTC: \${btc:,.2f}')
"

# Create directories
echo ""
echo "📁 Creating directories..."
mkdir -p logs data/signals data/trades data/analysis

# Start supervisor
echo ""
echo "🤖 Starting trading agent army..."
echo "   Press Ctrl+C to stop"
echo ""
python3 supervisor.py
