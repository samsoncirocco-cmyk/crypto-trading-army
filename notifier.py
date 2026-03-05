#!/usr/bin/env python3
"""
Telegram Notifier Module
Sends trade alerts, daily summaries, and error notifications via Telegram Bot.
Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.
"""

import os
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional

import aiohttp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Telegram notification handler for trading bot alerts.
    
    Environment Variables:
        TELEGRAM_BOT_TOKEN: Bot token from @BotFather
        TELEGRAM_CHAT_ID: Chat ID to send messages to
    
    Usage:
        notifier = TelegramNotifier()
        notifier.send_trade_alert('BTC', 5.0, 45000.0)
    """
    
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.enabled = bool(self.bot_token and self.chat_id)
        
        if not self.enabled:
            logger.warning(
                "Telegram notifier disabled. "
                "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars to enable."
            )
        else:
            logger.info("Telegram notifier enabled")
    
    def _escape_markdown(self, text: str) -> str:
        """Escape special characters for Telegram MarkdownV2"""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    async def _send_message(self, text: str, parse_mode: str = 'MarkdownV2') -> bool:
        """Send message via Telegram Bot API"""
        if not self.enabled:
            logger.debug(f"Would send: {text[:100]}...")
            return True
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        payload = {
            'chat_id': self.chat_id,
            'text': text,
            'parse_mode': parse_mode
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=30) as response:
                    if response.status == 200:
                        logger.debug("Message sent successfully")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to send message: {response.status} - {error_text}")
                        return False
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False
    
    def send_message(self, text: str, parse_mode: str = 'MarkdownV2') -> bool:
        """Synchronous wrapper for _send_message"""
        if not self.enabled:
            return True
        try:
            return asyncio.run(self._send_message(text, parse_mode))
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    def send_trade_alert(
        self,
        product_id: str,
        amount: float,
        price: float,
        order_id: Optional[str] = None,
        is_paper: bool = True
    ) -> bool:
        """
        Send trade execution alert.
        
        Args:
            product_id: Trading pair (e.g., 'BTC-USD')
            amount: Amount bought in USD
            price: Price per unit
            order_id: Optional order ID
            is_paper: Whether this is a paper trade
        """
        asset = product_id.split('-')[0]
        qty = amount / price if price > 0 else 0
        
        mode_emoji = '📋' if is_paper else '💰'
        mode_text = 'PAPER' if is_paper else 'LIVE'
        
        message = (
            f"{self._escape_markdown(mode_emoji)} *Trade Alert* \({mode_text}\)\n"
            f"\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\n"
            f"*Asset:* {self._escape_markdown(asset)}\n"
            f"*Amount:* ${amount:.2f}\n"
            f"*Price:* ${price:,.2f}\n"
            f"*Quantity:* {qty:.8f} {self._escape_markdown(asset)}\n"
        )
        
        if order_id:
            message += f"*Order ID:* `{self._escape_markdown(order_id)}`\n"
        
        message += f"\n⏱ _{self._escape_markdown(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))}_"
        
        return self.send_message(message)
    
    def send_dip_alert(
        self,
        product_id: str,
        price_change: float,
        current_price: float,
        extra_amount: float
    ) -> bool:
        """
        Send dip detected alert.
        
        Args:
            product_id: Trading pair
            price_change: Price change percentage (negative)
            current_price: Current asset price
            extra_amount: Additional amount being bought
        """
        asset = product_id.split('-')[0]
        
        message = (
            f"🎯 *Dip Detected*\n"
            f"\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\n"
            f"*{self._escape_markdown(asset)}* dropped {self._escape_markdown(f'{price_change:.2%}')}\n"
            f"*Current Price:* ${current_price:,.2f}\n"
            f"*Extra Buy:* +${extra_amount:.2f}\n"
            f"\n💡 Buying the dip\!"
        )
        
        return self.send_message(message)
    
    def send_daily_summary(
        self,
        portfolio_value: float,
        cash_balance: float,
        positions: list,
        daily_pnl: float,
        trades_today: int
    ) -> bool:
        """
        Send daily portfolio summary.
        
        Args:
            portfolio_value: Total portfolio value in USD
            cash_balance: USD cash balance
            positions: List of position dicts with asset, quantity, value, unrealized_pnl_pct
            daily_pnl: Today's profit/loss
            trades_today: Number of trades executed today
        """
        pnl_emoji = "🟢" if daily_pnl >= 0 else "🔴"
        
        message = (
            f"📊 *Daily Summary*\n"
            f"\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\n"
            f"*Portfolio Value:* ${portfolio_value:,.2f}\n"
            f"*Cash:* ${cash_balance:,.2f}\n"
            f"*Deployed:* ${portfolio_value - cash_balance:,.2f}\n"
            f"*Daily P&L:* {pnl_emoji} ${daily_pnl:+.2f}\n"
            f"*Trades Today:* {trades_today}\n"
        )
        
        if positions:
            message += "\n*Positions:*\n"
            for pos in positions[:5]:  # Limit to 5 positions
                emoji = "🟢" if pos.get('unrealized_pnl_pct', 0) >= 0 else "🔴"
                message += (
                    f"  {pos['asset']}: "
                    f"${pos.get('value', 0):,.2f} "
                    f"({emoji} {pos.get('unrealized_pnl_pct', 0):+.1f}%)\n"
                )
        else:
            message += "\n_No positions_"
        
        message += f"\n⏱ _{self._escape_markdown(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))}_"
        
        return self.send_message(message)
    
    def send_error_alert(self, error_message: str, context: Optional[str] = None) -> bool:
        """
        Send error notification.
        
        Args:
            error_message: The error that occurred
            context: Optional context about what was happening
        """
        message = (
            f"⚠️ *Trading Bot Error*\n"
            f"\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\n"
            f"```\n{self._escape_markdown(error_message[:500])}\n```"
        )
        
        if context:
            message += f"\n*Context:* {self._escape_markdown(context)}"
        
        message += f"\n\n⏱ _{self._escape_markdown(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))}_"
        
        return self.send_message(message)
    
    def send_risk_alert(self, message: str, severity: str = 'warning') -> bool:
        """
        Send risk-related alert.
        
        Args:
            message: Risk alert message
            severity: 'warning' or 'critical'
        """
        emoji = "🚨" if severity == 'critical' else "⚡"
        
        message_text = (
            f"{self._escape_markdown(emoji)} *Risk Alert*\n"
            f"\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\n"
            f"{self._escape_markdown(message)}"
        )
        
        return self.send_message(message_text)
    
    def send_start_notification(self) -> bool:
        """Send bot startup notification"""
        mode = "📋 PAPER" if os.getenv('PAPER_MODE', 'true').lower() == 'true' else "💰 LIVE"
        
        message = (
            f"🤖 *Trading Bot Started*\n"
            f"\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\n"
            f"*Mode:* {self._escape_markdown(mode)}\n"
            f"*Time:* {self._escape_markdown(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))}\n"
            f"\n✅ Bot is running and monitoring markets"
        )
        
        return self.send_message(message)
    
    def send_stop_notification(self) -> bool:
        """Send bot shutdown notification"""
        message = (
            f"🛑 *Trading Bot Stopped*\n"
            f"\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\n"
            f"*Time:* {self._escape_markdown(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))}\n"
            f"\n💤 Bot has been shut down"
        )
        
        return self.send_message(message)


if __name__ == '__main__':
    # Test the notifier
    notifier = TelegramNotifier()
    
    if notifier.enabled:
        print("✅ Telegram notifier is enabled")
        print(f"   Chat ID: {notifier.chat_id}")
        
        # Test messages
        print("\nSending test alerts...")
        notifier.send_trade_alert('BTC-USD', 5.0, 45000.0, 'test-order-123', is_paper=True)
        notifier.send_dip_alert('BTC-USD', -0.05, 43000.0, 5.0)
    else:
        print("⚠️  Telegram notifier is disabled")
        print("   Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to enable")
