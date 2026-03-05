#!/usr/bin/env python3
"""
Execution Bot - Places trades on Coinbase
"""
import os, json, time, signal, sys
from pathlib import Path
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')
logger = logging.getLogger('executor')

BASE_DIR = Path(__file__).parent.parent
QUEUE_FILE = BASE_DIR / "data" / "trade_queue.jsonl"
TRADES_DIR = BASE_DIR / "data" / "trades"
RUNNING = True

try:
    sys.path.insert(0, str(BASE_DIR))
    from coinbase_advanced import CoinbaseAdvancedClient
    COINBASE_AVAILABLE = True
except Exception as e:
    logger.error(f"Coinbase not available: {e}")
    COINBASE_AVAILABLE = False

signal.signal(signal.SIGTERM, lambda s,f: globals().update(RUNNING=False))
signal.signal(signal.SIGINT, lambda s,f: globals().update(RUNNING=False))

def get_queued_trades():
    """Read trades from queue"""
    if not QUEUE_FILE.exists():
        return []
    trades = []
    with open(QUEUE_FILE) as f:
        for line in f:
            try: trades.append(json.loads(line))
            except: pass
    return trades

def check_daily_limit():
    """Check if we've hit 3 trades today"""
    today = datetime.now(timezone.utc).date().isoformat()
    count = 0
    for trade_file in TRADES_DIR.glob('trade_*.json'):
        try:
            with open(trade_file) as f:
                trade = json.load(f)
            if trade.get('timestamp', '').startswith(today):
                count += 1
        except: pass
    return count < 3

def execute_trade(trade):
    """Execute a trade (paper or live)"""
    paper_mode = os.getenv('PAPER_MODE', 'true').lower() == 'true'
    
    trade_record = {
        'trade_id': f"trade_{int(time.time())}_{trade['asset']}",
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'asset': trade['asset'],
        'direction': trade['direction'],
        'entry_price': trade['entry_price'],
        'stop_loss': trade.get('stop_loss'),
        'take_profit': trade.get('take_profit'),
        'confidence': trade.get('confidence'),
        'status': 'EXECUTED',
        'paper_mode': paper_mode
    }
    
    if paper_mode:
        logger.info(f"📋 PAPER TRADE: {trade['direction']} {trade['asset']} @ ${trade['entry_price']}")
    else:
        logger.info(f"🚀 LIVE TRADE: {trade['direction']} {trade['asset']} @ ${trade['entry_price']}")
        # Here would go actual Coinbase order placement
        if COINBASE_AVAILABLE:
            try:
                client = CoinbaseAdvancedClient()
                # client.place_market_order(...)
                logger.info("Coinbase order would be placed here")
            except Exception as e:
                logger.error(f"Coinbase error: {e}")
                trade_record['status'] = 'FAILED'
    
    TRADES_DIR.mkdir(parents=True, exist_ok=True)
    with open(TRADES_DIR / f"{trade_record['trade_id']}.json", 'w') as f:
        json.dump(trade_record, f, indent=2)
    
    return trade_record

def main():
    global RUNNING
    logger.info("="*60 + "\n🚀 EXECUTION BOT STARTED\n" + "="*60)
    logger.info(f"Mode: {'PAPER' if os.getenv('PAPER_MODE','true').lower()=='true' else 'LIVE'}")
    logger.info(f"Daily limit: 3 trades")
    
    executed = set()
    while RUNNING:
        try:
            if not check_daily_limit():
                logger.warning("Daily trade limit reached (3 trades)")
                time.sleep(60)
                continue
            
            trades = get_queued_trades()
            for trade in trades:
                trade_key = f"{trade.get('timestamp')}_{trade.get('asset')}"
                if trade_key in executed:
                    continue
                
                execute_trade(trade)
                executed.add(trade_key)
            
            time.sleep(10)
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()
