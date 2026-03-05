#!/bin/bash
set -euo pipefail

# Master launcher for trading agent army

BASE_DIR="$HOME/.openclaw/workspace/execution/trading"
LOCK_DIR="$BASE_DIR/data/locks"
LOCK_FILE="$LOCK_DIR/deploy_army.lock"

cd "$BASE_DIR"
mkdir -p logs data/signals data/analysis data/trades "$LOCK_DIR"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "deploy_army is already running"
    exit 0
fi

echo "DEPLOYING AGENT ARMY..."

is_running() {
    local script=$1
    pgrep -f "$BASE_DIR/$script" > /dev/null
}

launch_agent() {
    local name=$1
    local script=$2

    if is_running "$script"; then
        echo "$name: already running"
        return
    fi

    nohup python3 "$script" >> "logs/${name}.log" 2>&1 &
    echo "$name: PID $!"
    sleep 1
}

launch_agent "btc_scout" "agents/btc_scout_robust.py"
launch_agent "sol_scout" "agents/sol_scout_robust.py"
launch_agent "eth_scout" "agents/eth_scout.py"
launch_agent "trend_analyst" "agents/trend_analyst.py"
launch_agent "risk_manager" "agents/risk_manager.py"
launch_agent "executor" "agents/execution_bot.py"
launch_agent "coordinator" "agent_coordinator.py"

echo
echo "AGENT ARMY DEPLOYED"
echo "Checking status in 5 seconds..."
sleep 5

is_running "agents/btc_scout_robust.py" && echo "OK BTC Scout" || echo "DOWN BTC Scout"
is_running "agents/sol_scout_robust.py" && echo "OK SOL Scout" || echo "DOWN SOL Scout"
is_running "agents/eth_scout.py" && echo "OK ETH Scout" || echo "DOWN ETH Scout"
is_running "agents/trend_analyst.py" && echo "OK Trend Analyst" || echo "DOWN Trend Analyst"
is_running "agents/risk_manager.py" && echo "OK Risk Manager" || echo "DOWN Risk Manager"
is_running "agents/execution_bot.py" && echo "OK Executor" || echo "DOWN Executor"
is_running "agent_coordinator.py" && echo "OK Coordinator" || echo "DOWN Coordinator"

echo
echo "Signal count: $(find data/signals -maxdepth 1 -name '*.json' 2>/dev/null | wc -l)"
echo "Trade count: $(find data/trades -maxdepth 1 -name '*.json' 2>/dev/null | wc -l)"
