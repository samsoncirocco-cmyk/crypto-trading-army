#!/usr/bin/env python3
"""
Execution Bot v3 - LIVE ORDER PLACEMENT
Places real orders on Coinbase
"""
import os, json, time, signal, logging, sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s',
    handlers=[logging.FileHandler(LOG_DIR / 'executor_live.log'), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger('executor-live')

BASE_DIR = Path(__file__).parent.parent
QUEUE_FILE = BASE_DIR / "data" / "trade_queue.jsonl"
TRADES_DIR = BASE_DIR / "data" / "trades"
RUNNING = True
signal.signal(signal.SIGTERM, lambda s,f: globals().update(RUNNING=False))
signal.signal(signal.SIGINT, lambda s,f: globals().update(RUNNING=False))

sys.path.insert(0, str(BASE_DIR))
from coinbase_legacy import CoinbaseLegacyClient

# HARD CODED SAFETY LIMITS
MAX_TRADES_PER_DAY = 3
MAX_POSITION_USD = 10  # $10 max per trade
DAILY_LOSS_LIMIT_USD = 5  # Halt if down $5

def get_today_trade_count():
    """Count today's trades"""
    today = datetime.now(timezone.utc).date().isoformat()
    count = 0
    for trade_file in TRADES_DIR.glob('trade_*.json'):
        try:
            with open(trade_file) as f:
                trade = json.load(f)
            if trade.get('timestamp', '').startswith(today):
                count += 1
        except: pass
    return count

def get_today_pnl():
    """Calculate today's P&L"""
    today = datetime.now(timezone.utc).date().isoformat()
    pnl = 0
    for trade_file in TRADES_DIR.glob('trade_*.json'):
        try:
            with open(trade_file) as f:
                trade = json.load(f)
            if trade.get('timestamp', '').startswith(today):
                pnl += trade.get('pnl', 0)
        except: pass
    return pnl

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

def clear_queue():
    """Clear the queue"""
    if QUEUE_FILE.exists():
        QUEUE_FILE.unlink()

def execute_trade(trade, client):
    """Execute a trade on Coinbase"""
    paper_mode = os.getenv('PAPER_MODE', 'true').lower() == 'true'
    
    asset = trade['asset']
    direction = trade['direction']
    
    # Safety checks
    if get_today_trade_count() >= MAX_TRADES_PER_DAY:
        logger.warning("🚫 Daily trade limit reached")
        return None
    
    today_pnl = get_today_pnl()
    if today_pnl <= -DAILY_LOSS_LIMIT_USD:
        logger.error(f"🛑 CIRCUIT BREAKER: Daily loss ${today_pnl:.2f} exceeds limit")
        return None
    
    # Calculate position size
    position_usd = min(MAX_POSITION_USD, trade.get('usd_amount', 10))
    
    trade_record = {
        'trade_id': f"trade_{int(time.time())}_{asset.replace('-', '')}",
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'asset': asset,
        'direction': direction,
        'entry_price': trade.get('entry_price'),
        'position_size_usd': position_usd,
        'stop_loss': trade.get('stop_loss'),
        'take_profit': trade.get('take_profit'),
        'confidence': trade.get('confidence'),
        'paper_mode': paper_mode,
        'status': 'PENDING'
    }
    
    if paper_mode:
        logger.info(f"📋 PAPER: {direction} ${position_usd} of {asset} @ ${trade.get('entry_price')}")
        trade_record['status'] = 'PAPER_EXECUTED'
        trade_record['order_id'] = f"paper_{trade_record['trade_id']}"
    else:
        logger.info(f"🚀 LIVE: {direction} ${position_usd} of {asset}")
        try:
            side = 'buy' if direction == 'LONG' else 'sell'
            order = client.place_market_order(asset, side, position_usd)
            trade_record['order_id'] = order.order_id
            trade_record['status'] = 'EXECUTED'
            logger.info(f"✅ Order placed: {order.order_id}")
        except Exception as e:
            logger.error(f"❌ Order failed: {e}")
            trade_record['status'] = 'FAILED'
            trade_record['error'] = str(e)
    
    # Save trade record
    TRADES_DIR.mkdir(parents=True, exist_ok=True)
    with open(TRADES_DIR / f"{trade_record['trade_id']}.json", 'w') as f:
        json.dump(trade_record, f, indent=2)
    
    return trade_record

def main():
    global RUNNING
    logger.info("="*60)
    logger.info("🚀 EXECUTION BOT LIVE")
    logger.info("="*60)
    
    paper_mode = os.getenv('PAPER_MODE', 'true').lower() == 'true'
    logger.info(f"Mode: {'PAPER' if paper_mode else 'LIVE'}")
    logger.info(f"Max trades/day: {MAX_TRADES_PER_DAY}")
    logger.info(f"Max position: ${MAX_POSITION_USD}")
    logger.info(f"Daily loss halt: ${DAILY_LOSS_LIMIT_USD}")
    
    try:
        client = CoinbaseLegacyClient()
        logger.info("✅ Coinbase connected")
    except Exception as e:
        logger.error(f"❌ Coinbase failed: {e}")
        return
    
    executed = set()
    
    while RUNNING:
        try:
            trades_today = get_today_trade_count()
            pnl_today = get_today_pnl()
            
            if trades_today >= MAX_TRADES_PER_DAY:
                logger.info(f"Trade limit reached ({trades_today}/{MAX_TRADES_PER_DAY})")
                time.sleep(60)
                continue
            
            if pnl_today <= -DAILY_LOSS_LIMIT_USD:
                logger.error(f"CIRCUIT BREAKER ACTIVE: ${pnl_today:.2f}")
                time.sleep(300)
                continue
            
            trades = get_queued_trades()
            for trade in trades:
                trade_key = f"{trade.get('timestamp')}_{trade.get('asset')}"
                if trade_key in executed:
                    continue
                
                result = execute_trade(trade, client)
                if result:
                    executed.add(trade_key)
            
            # Clear processed trades from queue
            if executed:
                clear_queue()
            
            time.sleep(10)
            
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(30)

if __name__ == '__main__':
    while True:
        try: main(); break
        except KeyboardInterrupt: break
        except Exception as e: 
            logger.critical(f"Crash: {e}")
            time.sleep(60)
