#!/usr/bin/env python3
"""
Telegram Alert Bot - Sends trade notifications
"""
import os, json, logging, sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('telegram-alerts')

# Telegram bot configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_telegram_message(message: str):
    """Send message via Telegram bot"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured - set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        return False
    
    try:
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send Telegram: {e}")
        return False

def alert_trade_entered(trade: dict):
    """Alert when trade entered"""
    emoji = "🚀" if trade.get('paper_mode') else "💰"
    mode = "PAPER" if trade.get('paper_mode') else "LIVE"
    
    msg = f"""{emoji} *TRADE ENTERED* ({mode})

*Asset:* {trade['asset']}
*Direction:* {trade['direction']}
*Entry:* ${trade['entry_price']:,.2f}
*Size:* ${trade.get('position_size_usd', 10)}

*Stop Loss:* ${trade.get('stop_loss', 0):,.2f}
*Take Profit:* ${trade.get('take_profit', 0):,.2f}

*Confidence:* {trade.get('confidence', 0):.0%}
*Time:* {trade.get('timestamp', 'now')}"""
    
    send_telegram_message(msg)
    logger.info(f"Trade alert sent: {trade['asset']} {trade['direction']}")

def alert_daily_summary(trades_today: int, pnl: float):
    """Daily performance summary"""
    emoji = "📈" if pnl >= 0 else "📉"
    sign = "+" if pnl >= 0 else ""
    
    msg = f"""{emoji} *DAILY SUMMARY*

*Trades:* {trades_today}
*P&L:* {sign}${pnl:.2f}

*Status:* {'Profitable' if pnl >= 0 else 'Loss'} day

Keep grinding."""
    
    send_telegram_message(msg)

def alert_error(error_msg: str):
    """Alert on critical errors"""
    msg = f"""🚨 *SYSTEM ALERT*

{error_msg}

Check logs immediately."""
    send_telegram_message(msg)

if __name__ == '__main__':
    # Test
    test_trade = {
        'asset': 'BTC-USD',
        'direction': 'LONG',
        'entry_price': 66267.99,
        'position_size_usd': 10,
        'stop_loss': 64942.63,
        'take_profit': 68918.71,
        'confidence': 0.85,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'paper_mode': True
    }
    alert_trade_entered(test_trade)
