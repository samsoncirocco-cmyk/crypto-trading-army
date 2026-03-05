"""
Risk management for trading bot
Enforces limits and validates trades
"""

import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
import json


class RiskManager:
    """
    Enforces trading limits and risk rules
    All limits are hardcoded - no overrides
    """
    
    # Hard limits (cannot be changed via config)
    MAX_DAILY_BUDGET = 10.0      # USD per day
    MAX_ORDER_SIZE = 10.0        # USD per order
    MAX_TOTAL_CAPITAL = 100.0    # USD total deployed
    DAILY_LOSS_LIMIT = 5.0       # Stop if daily loss exceeds
    WEEKLY_LOSS_LIMIT = 15.0     # Stop if weekly loss exceeds
    
    ALLOWED_PAIRS = ['BTC-USD', 'ETH-USD', 'SOL-USD']
    
    DATA_DIR = Path(__file__).parent / 'data'
    
    def __init__(self):
        self.DATA_DIR.mkdir(exist_ok=True)
        self._check_trading_halt()
    
    def _check_trading_halt(self):
        """Check if emergency halt file exists"""
        halt_file = self.DATA_DIR / 'HALT'
        if halt_file.exists():
            raise TradingHaltedError("Trading halted. Remove data/HALT to resume.")
    
    def _get_daily_stats(self) -> dict:
        """Get today's trading stats"""
        date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        filepath = self.DATA_DIR / f'daily_stats_{date_str}.json'
        
        if filepath.exists():
            with open(filepath) as f:
                return json.load(f)
        
        return {
            'date': date_str,
            'orders_placed': 0,
            'usd_spent': 0.0,
            'realized_pnl': 0.0
        }
    
    def _save_daily_stats(self, stats: dict):
        """Save daily stats"""
        date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        filepath = self.DATA_DIR / f'daily_stats_{date_str}.json'
        
        with open(filepath, 'w') as f:
            json.dump(stats, f, indent=2)
    
    def validate_order(self, pair: str, amount_usd: float, side: str = 'BUY') -> bool:
        """
        Validate if order complies with risk rules
        
        Returns True if allowed, raises RiskViolation if not
        """
        # Check trading pair
        if pair not in self.ALLOWED_PAIRS:
            raise RiskViolation(f"Pair {pair} not allowed. Allowed: {self.ALLOWED_PAIRS}")
        
        # Check order size
        if amount_usd > self.MAX_ORDER_SIZE:
            raise RiskViolation(f"Order ${amount_usd} exceeds max ${self.MAX_ORDER_SIZE}")
        
        if amount_usd <= 0:
            raise RiskViolation("Order amount must be positive")
        
        # Check daily budget for buys
        if side == 'BUY':
            stats = self._get_daily_stats()
            if stats['usd_spent'] + amount_usd > self.MAX_DAILY_BUDGET:
                raise RiskViolation(
                    f"Daily budget exceeded. Spent: ${stats['usd_spent']:.2f}, "
                    f"Max: ${self.MAX_DAILY_BUDGET:.2f}"
                )
        
        return True
    
    def record_order(self, pair: str, amount_usd: float, side: str = 'BUY'):
        """Record an executed order in daily stats"""
        stats = self._get_daily_stats()
        stats['orders_placed'] += 1
        
        if side == 'BUY':
            stats['usd_spent'] += amount_usd
        
        self._save_daily_stats(stats)
    
    def record_pnl(self, pnl: float):
        """Record realized P&L"""
        stats = self._get_daily_stats()
        stats['realized_pnl'] += pnl
        self._save_daily_stats(stats)
        
        # Check if we hit daily loss limit
        if stats['realized_pnl'] < -self.DAILY_LOSS_LIMIT:
            self._emergency_halt(f"Daily loss limit hit: ${stats['realized_pnl']:.2f}")
    
    def _emergency_halt(self, reason: str):
        """Emergency halt all trading"""
        halt_file = self.DATA_DIR / 'HALT'
        halt_file.write_text(f"{reason}\n{datetime.now(timezone.utc).isoformat()}")
        raise TradingHaltedError(f"EMERGENCY HALT: {reason}")
    
    def get_status(self) -> dict:
        """Get current risk status"""
        stats = self._get_daily_stats()
        halt_file = self.DATA_DIR / 'HALT'
        
        return {
            'trading_allowed': not halt_file.exists(),
            'daily_spent': stats['usd_spent'],
            'daily_remaining': self.MAX_DAILY_BUDGET - stats['usd_spent'],
            'daily_pnl': stats['realized_pnl'],
            'orders_today': stats['orders_placed']
        }
    
    def halt(self, reason: str = "Manual halt"):
        """Manually halt trading"""
        self._emergency_halt(reason)
    
    def resume(self):
        """Resume trading (remove halt file)"""
        halt_file = self.DATA_DIR / 'HALT'
        if halt_file.exists():
            halt_file.unlink()


class RiskViolation(Exception):
    """Raised when a trade violates risk rules"""
    pass


class TradingHaltedError(Exception):
    """Raised when trading is halted"""
    pass
