#!/bin/bash
# install-cron.sh - Install trading bot as cron jobs for persistence
# Run: ./install-cron.sh

CRON_FILE="/tmp/trading-cron"
TRADING_DIR="$HOME/.openclaw/workspace/execution/trading"

echo "=========================================="
echo "📅 Installing Trading Bot Cron Jobs"
echo "=========================================="

# Create cron entries
cat > $CRON_FILE << 'EOF'
# Trading Bot Army - Cron Schedule
# Scouts run every minute (fetch prices)
* * * * * cd TRADING_DIR && python3 agents/btc_scout_live.py >> logs/btc.log 2>&1
* * * * * cd TRADING_DIR && python3 agents/sol_scout_live.py >> logs/sol.log 2>&1
* * * * * cd TRADING_DIR && python3 agents/eth_scout_live.py >> logs/eth.log 2>&1

# Coordinator processes signals every 2 minutes
*/2 * * * * cd TRADING_DIR && python3 agent_coordinator_v2.py >> logs/coordinator.log 2>&1

# Executor checks queue every minute
* * * * * cd TRADING_DIR && python3 agents/execution_bot_v3.py >> logs/executor.log 2>&1

# Risk manager monitors limits every 5 minutes
*/5 * * * * cd TRADING_DIR && python3 agents/risk_manager.py >> logs/risk.log 2>&1

# Auditor reports performance every hour
0 * * * * cd TRADING_DIR && python3 agents/auditor.py >> logs/auditor.log 2>&1
EOF

# Replace placeholder with actual path
sed -i.bak "s|TRADING_DIR|$TRADING_DIR|g" $CRON_FILE

# Install cron jobs
crontab $CRON_FILE

echo ""
echo "✅ Cron jobs installed!"
echo ""
echo "Current cron jobs:"
crontab -l | grep -v "^#" | grep -v "^$" | head -10

echo ""
echo "📊 Logs will be written to: $TRADING_DIR/logs/"
echo ""
echo "To remove: crontab -r"
echo "To edit: crontab -e"

rm $CRON_FILE $CRON_FILE.bak
