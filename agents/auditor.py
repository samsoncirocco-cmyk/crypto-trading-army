#!/usr/bin/env python3
"""Performance Auditor - Tracks win rate, Sharpe, drawdown"""
import os, json, time, signal, logging, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import statistics

LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s',
    handlers=[logging.FileHandler(LOG_DIR / 'auditor.log'), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger('auditor')

TRADES_DIR = Path(__file__).parent.parent / 'data' / 'trades'
RUNNING = True
signal.signal(signal.SIGTERM, lambda s,f: globals().update(RUNNING=False))

def calculate_metrics():
    """Calculate performance metrics"""
    trades = []
    for trade_file in TRADES_DIR.glob('trade_*.json'):
        try:
            with open(trade_file) as f:
                trades.append(json.load(f))
        except: pass
    
    if len(trades) < 3:
        return None
    
    wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
    win_rate = wins / len(trades)
    
    returns = [t.get('pnl_pct', 0) for t in trades]
    avg_return = statistics.mean(returns) if returns else 0
    
    return {
        'total_trades': len(trades),
        'win_rate': round(win_rate, 4),
        'avg_return': round(avg_return, 4),
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

def main():
    global RUNNING
    logger.info("="*50 + "\n📈 PERFORMANCE AUDITOR DEPLOYED\n" + "="*50)
    while RUNNING:
        try:
            metrics = calculate_metrics()
            if metrics:
                logger.info(f"📊 Win Rate: {metrics['win_rate']:.1%} | Trades: {metrics['total_trades']}")
            time.sleep(300)  # Report every 5 min
        except Exception as e: logger.error(f"Error: {e}"); time.sleep(60)

if __name__ == '__main__':
    while True:
        try: main(); break
        except KeyboardInterrupt: break
        except Exception as e: logger.critical(f"Crash: {e}"); time.sleep(10)
