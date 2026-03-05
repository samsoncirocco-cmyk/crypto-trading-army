#!/usr/bin/env python3
"""Daily Reporter - End of day summary"""
import os, json, time, signal, logging, sys
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s',
    handlers=[logging.FileHandler(LOG_DIR / 'reporter.log'), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger('reporter')

TRADES_DIR = Path(__file__).parent.parent / 'data' / 'trades'
RUNNING = True
signal.signal(signal.SIGTERM, lambda s,f: globals().update(RUNNING=False))

def generate_daily_report():
    """Generate end of day report"""
    today = datetime.now(timezone.utc).date().isoformat()
    trades = []
    for trade_file in TRADES_DIR.glob('trade_*.json'):
        try:
            with open(trade_file) as f:
                t = json.load(f)
            if t.get('timestamp', '').startswith(today):
                trades.append(t)
        except: pass
    
    pnl = sum(t.get('pnl', 0) for t in trades)
    logger.info("="*50)
    logger.info(f"📋 DAILY REPORT: {today}")
    logger.info(f"   Trades: {len(trades)}")
    logger.info(f"   P&L: ${pnl:+.2f}")
    logger.info("="*50)

def main():
    global RUNNING
    logger.info("="*50 + "\n📋 DAILY REPORTER DEPLOYED\n" + "="*50)
    while RUNNING:
        try:
            now = datetime.now(timezone.utc)
            if now.hour == 18 and now.minute < 5:  # 6 PM
                generate_daily_report()
            time.sleep(300)
        except Exception as e: logger.error(f"Error: {e}"); time.sleep(60)

if __name__ == '__main__':
    while True:
        try: main(); break
        except KeyboardInterrupt: break
        except Exception as e: logger.critical(f"Crash: {e}"); time.sleep(10)
