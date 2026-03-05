#!/bin/bash
# quick-start.sh - Get up and running in 60 seconds

echo "🚀 CRYPTO GOD JOHN - QUICK START"
echo ""

# Check directory
if [ ! -f "coinbase_legacy.py" ]; then
    echo "❌ Run this from the trading directory:"
    echo "   cd ~/.openclaw/workspace/execution/trading"
    exit 1
fi

# Check .env
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found!"
    echo "Creating from example..."
    cat > .env << 'EOF'
# Coinbase API Credentials
# Get from: https://pro.coinbase.com/profile/api
COINBASE_API_KEY_NAME=your_key_here
COINBASE_API_PRIVATE_KEY=your_secret_here

# Safety Settings
PAPER_MODE=true
EOF
    echo "✅ Created .env - EDIT IT NOW with your credentials"
    exit 1
fi

# Test connection
echo "🔌 Testing Coinbase connection..."
python3 -c "
from dotenv import load_dotenv
load_dotenv()
from coinbase_legacy import CoinbaseLegacyClient
c = CoinbaseLegacyClient()
print(f'✅ Connected - BTC: \${c.get_product_price(\"BTC-USD\"):,.0f}')
"

if [ $? -ne 0 ]; then
    echo "❌ Connection failed - check .env credentials"
    exit 1
fi

# Create directories
mkdir -p logs data/signals data/trades

# Run test suite
echo ""
echo "🧪 Running test suite..."
python3 test_suite.py

# Start bot
echo ""
echo "🤖 Starting trading bot..."
echo "   Press Ctrl+C to stop"
echo ""
python3 supervisor.py
