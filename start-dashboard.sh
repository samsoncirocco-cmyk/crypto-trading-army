#!/bin/bash
# start-dashboard.sh - Start web dashboard in background

echo "🌐 Starting Trading Dashboard..."
echo "   URL: http://localhost:8080"
echo ""

cd ~/.openclaw/workspace/execution/trading
python3 dashboard.py &

sleep 2
echo "✅ Dashboard running"
echo "   Open: http://localhost:8080"
echo ""
echo "To stop: pkill -f dashboard.py"
