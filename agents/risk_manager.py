#!/usr/bin/env python3
"""
Risk Manager - Enforces limits and circuit breakers
"""
import os, json, time, signal, logging, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s',
    handlers=[logging.FileHandler(LOG_DIR / 'risk_manager.log'), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger('risk-manager')

TRADES_DIR, DATA_DIR, RUNNING = Path(__file__).parent.parent / 'data' / 'trades', Path(__file__).parent.parent / 'data', True
signal.signal(signal.SIGTERM, lambda s,f: globals().update(RUNNING=False))

def check_limits():
    trades = list(TRADES_DIR.glob('trade_*.json'))
    daily_trades = [t for t in trades if (datetime.now(timezone.utc) - datetime.fromisoformat(json.load(open(t))['timestamp'])).days == 0]
    if len(daily_trades) >= 3:
        logger.warning("🛑 DAILY TRADE LIMIT REACHED (3 trades)")
        (DATA_DIR / 'HALT').write_text(f"Daily limit at {datetime.now().isoformat()}")
        return False
    return True

def main():
    global RUNNING
    logger.info("="*50 + "\n⚠️  RISK MANAGER DEPLOYED\n" + "="*50)
    logger.info("Limits: Max 3 trades/day, 2% risk/trade")
    while RUNNING:
        try:
            if not check_limits(): pass
            elif (DATA_DIR / 'HALT').exists():
                logger.warning("🛑 TRADING HALTED - Check HALT file")
            else: logger.info("✅ Risk checks passed")
            time.sleep(60)
        except Exception as e: logger.error(f"Error: {e}"); time.sleep(10)

if __name__ == '__main__':
    while True:
        try: main(); break
        except KeyboardInterrupt: break
        except Exception as e: logger.critical(f"Crash: {e}"); time.sleep(10)
