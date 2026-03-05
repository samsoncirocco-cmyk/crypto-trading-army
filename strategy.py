#!/usr/bin/env python3
"""
Trading Strategy Module
Implements Dollar Cost Averaging (DCA) strategy with optional dip buying.
"""

import os
import json
import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Callable, Dict, List
from dataclasses import dataclass, asdict

from coinbase_advanced import CoinbaseAdvancedClient, CoinbaseAPIError
from portfolio import PortfolioTracker
from risk import RiskManager, RiskViolation, TradingHaltedError


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PricePoint:
    """Represents a price snapshot"""
    timestamp: str
    price: float
    product_id: str


@dataclass
class TradeResult:
    """Result of a trade execution"""
    success: bool
    order_id: Optional[str]
    amount: float
    product_id: str
    price: Optional[float]
    error: Optional[str]
    timestamp: str


class DCAStrategy:
    """
    Dollar Cost Averaging Strategy
    
    Buys a fixed amount daily with optional increased buying on price dips.
    All trades respect risk limits from risk.py.
    
    Args:
        daily_amount: Amount to buy daily in USD (default $5)
        product_id: Trading pair (default BTC-USD)
        dip_threshold: Price drop % to trigger extra buy (default 3%)
        dip_multiplier: Extra amount to buy on dips (default 2x)
        price_history_hours: Hours of price history to keep (default 24)
    """
    
    DATA_DIR = Path(__file__).parent / 'data'
    
    def __init__(
        self,
        daily_amount: float = 5.0,
        product_id: str = 'BTC-USD',
        dip_threshold: float = 0.03,
        dip_multiplier: float = 2.0,
        price_history_hours: int = 24
    ):
        self.daily_amount = min(daily_amount, 10.0)  # Enforce max $10/order
        self.product_id = product_id
        self.dip_threshold = dip_threshold
        self.dip_multiplier = dip_multiplier
        self.price_history_hours = price_history_hours
        
        self.client = CoinbaseAdvancedClient()
        self.portfolio = PortfolioTracker(self.client)
        self.risk = RiskManager()
        
        self.DATA_DIR.mkdir(exist_ok=True)
        self.price_history: List[PricePoint] = []
        
        self._load_state()
    
    def _get_state_file(self) -> Path:
        """Get state file path for this strategy"""
        return self.DATA_DIR / f'dca_state_{self.product_id.replace("-", "_")}.json'
    
    def _load_state(self):
        """Load persisted state"""
        state_file = self._get_state_file()
        if state_file.exists():
            try:
                with open(state_file) as f:
                    state = json.load(f)
                    self.price_history = [
                        PricePoint(**p) for p in state.get('price_history', [])
                    ]
                    logger.info(f"Loaded state with {len(self.price_history)} price points")
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")
    
    def _save_state(self):
        """Persist state to disk"""
        state = {
            'last_updated': datetime.now(timezone.utc).isoformat(),
            'price_history': [asdict(p) for p in self.price_history]
        }
        state_file = self._get_state_file()
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def get_current_price(self) -> Optional[float]:
        """Get current price and track in history"""
        try:
            price = self.client.get_product_price(self.product_id)
            
            # Record price point
            point = PricePoint(
                timestamp=datetime.now(timezone.utc).isoformat(),
                price=price,
                product_id=self.product_id
            )
            self.price_history.append(point)
            
            # Trim old history
            cutoff = datetime.now(timezone.utc) - timedelta(hours=self.price_history_hours)
            self.price_history = [
                p for p in self.price_history 
                if datetime.fromisoformat(p.timestamp) > cutoff
            ]
            
            self._save_state()
            return price
            
        except Exception as e:
            logger.error(f"Failed to get price: {e}")
            return None
    
    def get_price_change_24h(self) -> Optional[float]:
        """
        Calculate 24h price change percentage.
        Returns None if insufficient history.
        """
        if len(self.price_history) < 2:
            return None
        
        # Get price from ~24h ago
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        old_prices = [p for p in self.price_history if datetime.fromisoformat(p.timestamp) < cutoff]
        
        if not old_prices:
            return None
        
        old_price = old_prices[0].price
        current_price = self.price_history[-1].price
        
        return (current_price - old_price) / old_price
    
    def check_dip(self) -> tuple[bool, float, Optional[float]]:
        """
        Check if price has dropped significantly.
        
        Returns: (is_dip, current_price, price_change_pct)
        """
        current_price = self.get_current_price()
        if current_price is None:
            return False, 0.0, None
        
        price_change = self.get_price_change_24h()
        if price_change is None:
            return False, current_price, None
        
        is_dip = price_change <= -self.dip_threshold
        return is_dip, current_price, price_change
    
    def calculate_buy_amount(self) -> tuple[float, str]:
        """
        Calculate how much to buy based on conditions.
        
        Returns: (amount_usd, reason)
        """
        is_dip, current_price, price_change = self.check_dip()
        
        if is_dip and price_change:
            # Buy more on dips (capped at $10)
            dip_amount = min(
                self.daily_amount * self.dip_multiplier,
                10.0  # Hard cap at $10
            )
            reason = f"Dip detected: {price_change:.2%} drop - buying ${dip_amount:.2f}"
            return dip_amount, reason
        else:
            reason = f"Regular DCA - buying ${self.daily_amount:.2f}"
            return self.daily_amount, reason
    
    def execute_buy(self, amount_usd: Optional[float] = None) -> TradeResult:
        """
        Execute a buy order.
        
        Args:
            amount_usd: Amount to buy (if None, uses DCA calculation)
        
        Returns:
            TradeResult with execution details
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        try:
            # Check if trading is halted
            self.risk._check_trading_halt()
        except TradingHaltedError as e:
            return TradeResult(
                success=False,
                order_id=None,
                amount=0.0,
                product_id=self.product_id,
                price=None,
                error=str(e),
                timestamp=timestamp
            )
        
        # Determine amount to buy
        if amount_usd is None:
            amount_usd, reason = self.calculate_buy_amount()
        else:
            reason = f"Manual buy of ${amount_usd:.2f}"
        
        logger.info(reason)
        
        try:
            # Validate against risk limits
            self.risk.validate_order(self.product_id, amount_usd, 'BUY')
            
            # Check portfolio balance
            if not self.portfolio.can_trade(amount_usd):
                error = f"Insufficient USD balance for ${amount_usd:.2f}"
                logger.error(error)
                return TradeResult(
                    success=False,
                    order_id=None,
                    amount=amount_usd,
                    product_id=self.product_id,
                    price=None,
                    error=error,
                    timestamp=timestamp
                )
            
            # Get current price for logging
            price = self.get_current_price()
            asset = self.product_id.split('-')[0]
            qty = amount_usd / price if price else 0
            
            # Execute the trade
            if not self.client.live_mode:
                logger.info(f"[PAPER] Would buy ${amount_usd:.2f} of {self.product_id} ({qty:.8f} {asset})")
                self.risk.record_order(self.product_id, amount_usd, 'BUY')
                return TradeResult(
                    success=True,
                    order_id="PAPER-ORDER",
                    amount=amount_usd,
                    product_id=self.product_id,
                    price=price,
                    error=None,
                    timestamp=timestamp
                )
            
            # Live trading
            logger.info(f"🚀 Placing market buy: ${amount_usd:.2f} of {self.product_id}")
            order = self.client.place_market_buy(self.product_id, amount_usd)
            
            if order:
                self.risk.record_order(self.product_id, amount_usd, 'BUY')
                logger.info(f"✅ Order placed: {order.order_id}")
                return TradeResult(
                    success=True,
                    order_id=order.order_id,
                    amount=amount_usd,
                    product_id=self.product_id,
                    price=price,
                    error=None,
                    timestamp=timestamp
                )
            else:
                error = "Order placement returned None"
                logger.error(error)
                return TradeResult(
                    success=False,
                    order_id=None,
                    amount=amount_usd,
                    product_id=self.product_id,
                    price=price,
                    error=error,
                    timestamp=timestamp
                )
        
        except RiskViolation as e:
            logger.error(f"Risk check failed: {e}")
            return TradeResult(
                success=False,
                order_id=None,
                amount=amount_usd,
                product_id=self.product_id,
                price=None,
                error=f"Risk violation: {e}",
                timestamp=timestamp
            )
        
        except CoinbaseAPIError as e:
            logger.error(f"API error: {e}")
            return TradeResult(
                success=False,
                order_id=None,
                amount=amount_usd,
                product_id=self.product_id,
                price=None,
                error=f"API error: {e}",
                timestamp=timestamp
            )
    
    def run_once(self) -> TradeResult:
        """Execute one DCA cycle"""
        logger.info(f"Running DCA strategy for {self.product_id}")
        
        # Update price before making decisions
        self.get_current_price()
        
        return self.execute_buy()
    
    def get_status(self) -> Dict:
        """Get current strategy status"""
        current_price = self.get_current_price()
        price_change = self.get_price_change_24h()
        is_dip, _, _ = self.check_dip() if current_price else (False, 0, None)
        
        risk_status = self.risk.get_status()
        
        return {
            'product_id': self.product_id,
            'daily_amount': self.daily_amount,
            'current_price': current_price,
            'price_change_24h': price_change,
            'is_dip': is_dip,
            'dip_threshold': self.dip_threshold,
            'price_history_count': len(self.price_history),
            'daily_remaining': risk_status['daily_remaining'],
            'trading_allowed': risk_status['trading_allowed']
        }
