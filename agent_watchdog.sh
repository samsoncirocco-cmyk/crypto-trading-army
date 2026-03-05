#!/bin/bash
# Agent Army Watchdog - Restart crashed agents

TRADING_DIR="$HOME/.openclaw/workspace/execution/trading"
LOG_DIR="$TRADING_DIR/logs"

while true; do
    # Check if agents are running
    BTC_COUNT=$(ps aux | grep btc_scout_simple | grep -v grep | wc -l)
    SOL_COUNT=$(ps aux | grep sol_scout | grep -v grep | wc -l)
    COORD_COUNT=$(ps aux | grep agent_coordinator | grep -v grep | wc -l)
    
    if [ "$BTC_COUNT" -eq 0 ]; then
        echo "$(date): BTC Scout down, restarting..." >> $LOG_DIR/watchdog.log
        cd $TRADING_DIR && python3 agents/btc_scout_simple.py >> logs/btc_scout_1.log 2>&1 &
    fi
    
    if [ "$SOL_COUNT" -eq 0 ]; then
        echo "$(date): SOL Scout down, restarting..." >> $LOG_DIR/watchdog.log
        cd $TRADING_DIR && python3 agents/sol_scout.py >> logs/sol_scout_1.log 2>&1 &
    fi
    
    if [ "$COORD_COUNT" -eq 0 ]; then
        echo "$(date): Coordinator down, restarting..." >> $LOG_DIR/watchdog.log
        cd $TRADING_DIR && python3 agent_coordinator.py >> logs/coordinator.log 2>&1 &
    fi
    
    sleep 10
done
