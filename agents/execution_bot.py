#!/usr/bin/env python3
"""
Execution Bot - Places paper trades
"""
import os, json, time, signal, logging, sys
from pathlib import Path
from datetime import datetime, timezone

LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s',
    handlers=[logging.FileHandler(LOG_DIR / 'executor.log'), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger('executor')

ANALYSIS_DIR, TRADES_DIR, RUNNING = Path(__file__).parent.parent / 'data' / 'analysis', Path(__file__).parent.parent / 'data' / 'trades', True
signal.signal(signal.SIGTERM, lambda s,f: globals().update(RUNNING=False))

def execute_trade(analysis_file):
    with open(analysis_file) as f:
        sig = json.load(f)
    if not sig.get('trend_aligned'): return False
    trade = {
        'trade_id': f"trade_{int(time.time())}",
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'asset': sig['asset'], 'direction': sig['direction'],
        'entry': sig['entry_price'], 'stop': sig['stop_loss'], 'target': sig['take_profit'],
        'status': 'OPEN', 'paper_mode': True
    }
    TRADES_DIR.mkdir(parents=True, exist_ok=True)
    with open(TRADES_DIR / f"{trade['trade_id']}.json", 'w') as f:
        json.dump(trade, f)
    logger.info(f"🚀 EXECUTED: {trade['direction']} {trade['asset']} @ ${trade['entry']:,.2f}")
    return True

def main():
    global RUNNING
    logger.info("="*50 + "\n🚀 EXECUTION BOT DEPLOYED (PAPER MODE)\n" + "="*50)
    trades_executed = 0
    while RUNNING:
        try:
            analyses = list(ANALYSIS_DIR.glob('analysis_*.json'))
            for analysis in analyses[-3:]:
                try:
                    if execute_trade(analysis): trades_executed += 1
                except: pass
            if trades_executed > 0 and trades_executed % 5 == 0:
                logger.info(f"Total trades executed: {trades_executed}")
            time.sleep(20)
        except Exception as e: logger.error(f"Error: {e}"); time.sleep(10)

if __name__ == '__main__':
    while True:
        try: main(); break
        except KeyboardInterrupt: break
        except Exception as e: logger.critical(f"Crash: {e}"); time.sleep(10)
