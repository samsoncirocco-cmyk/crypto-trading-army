#!/bin/bash
# EMERGENCY_HALT.sh - Stop all trading immediately

echo "🛑 EMERGENCY HALT"
echo "=================="
echo ""

# Kill all trading processes
pkill -f "scout" 2>/dev/null && echo "✅ Scouts stopped"
pkill -f "executor" 2>/dev/null && echo "✅ Executors stopped"
pkill -f "coordinator" 2>/dev/null && echo "✅ Coordinator stopped"
pkill -f "supervisor" 2>/dev/null && echo "✅ Supervisor stopped"

# Remove cron jobs
crontab -r 2>/dev/null && echo "✅ Cron jobs removed"

echo ""
echo "All trading activity halted."
echo ""
echo "To resume: ./quick-start.sh"
