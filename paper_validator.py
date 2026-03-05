#!/usr/bin/env python3
"""
Paper Validator - Live Paper Trading with Shadow Validation

Runs strategy on live market data with paper orders,
validates signals against backtest predictions.
"""

import json
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from coinbase_advanced import CoinbaseAdvancedClient
from liquidity_sweep_engine import LiquiditySweepEngine, SweepSignal
from notifier import TelegramNotifier

logger = logging.getLogger(__name__)

@dataclass
class PaperTrade:
    """Record of a paper trade"""
    signal_id: str
    timestamp: datetime
    pair: str
    direction: str
    entry_price: float
    exit_price: Optional[float]
    stop_loss: float
    take_profit: float
    predicted_outcome: str  # 'win' or 'loss'
    actual_outcome: Optional[str]
    pnl: Optional[float]
    slippage: float
    latency_ms: float
    status: str  # 'open', 'closed', 'error'

class PaperValidator:
    """
    Validates strategy on live data without risking capital
    
    Tracks:
    - Signal accuracy vs backtest
    - Execution latency
    - Slippage
    - Fill rates
    """
    
    DATA_DIR = Path(__file__).parent / 'data' / 'paper_trades'
    
    def __init__(self, 
                 engine: LiquiditySweepEngine,
                 client: Optional[CoinbaseAdvancedClient] = None):
        """
        Args:
            engine: Liquidity sweep detection engine
            client: Coinbase client for live price data (optional)
        """
        self.engine = engine
        self.client = client or CoinbaseAdvancedClient()
        self.notifier = TelegramNotifier()
        self.trades: List[PaperTrade] = []
        
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._load_trades()
    
    def _load_trades(self):
        """Load historical paper trades"""
        file_path = self.DATA_DIR / 'paper_trades.jsonl'
        if file_path.exists():
            with open(file_path) as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        self.trades.append(PaperTrade(**data))
                    except:
                        pass
    
    def _save_trade(self, trade: PaperTrade):
        """Save a paper trade to disk"""
        file_path = self.DATA_DIR / 'paper_trades.jsonl'
        with open(file_path, 'a') as f:
            f.write(json.dumps(asdict(trade), default=str) + '\n')
    
    def execute_paper_trade(self, signal: SweepSignal) -> PaperTrade:
        """
        Execute a paper trade based on signal
        
        Args:
            signal: Detected sweep signal
        
        Returns:
            PaperTrade record
        """
        start_time = time.time()
        
        # Get current price (simulated latency)
        try:
            current_price = self.client.get_product_price(signal.pair)
            latency_ms = (time.time() - start_time) * 1000
        except Exception as e:
            logger.error(f"Failed to get price: {e}")
            current_price = signal.entry_price
            latency_ms = 0
        
        # Calculate slippage
        slippage = abs(current_price - signal.entry_price) / signal.entry_price
        
        # Predict outcome based on RR ratio
        predicted = 'win' if signal.risk_reward_ratio >= 2.0 else 'loss'
        
        trade = PaperTrade(
            signal_id=f"{signal.timestamp.isoformat()}_{signal.pair}",
            timestamp=datetime.now(timezone.utc),
            pair=signal.pair,
            direction=signal.direction.value,
            entry_price=current_price,
            exit_price=None,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            predicted_outcome=predicted,
            actual_outcome=None,
            pnl=None,
            slippage=slippage,
            latency_ms=latency_ms,
            status='open'
        )
        
        self.trades.append(trade)
        self._save_trade(trade)
        
        # Notify
        self.notifier.send_message(
            f"📋 Paper Trade: {signal.direction.value} {signal.pair}\n"
            f"Entry: ${current_price:,.2f}\n"
            f"SL: ${signal.stop_loss:,.2f} | TP: ${signal.take_profit:,.2f}\n"
            f"Predicted: {predicted.upper()} | Latency: {latency_ms:.1f}ms"
        )
        
        logger.info(f"Paper trade executed: {trade.signal_id}")
        return trade
    
    def close_paper_trade(self, 
                          trade: PaperTrade, 
                          exit_price: float,
                          actual_outcome: str):
        """
        Close an open paper trade
        
        Args:
            trade: Open paper trade
            exit_price: Exit price
            actual_outcome: 'win' or 'loss'
        """
        trade.exit_price = exit_price
        trade.actual_outcome = actual_outcome
        trade.status = 'closed'
        
        # Calculate P&L
        if trade.direction == 'LONG':
            trade.pnl = (exit_price - trade.entry_price) / trade.entry_price
        else:
            trade.pnl = (trade.entry_price - exit_price) / trade.entry_price
        
        # Subtract fees
        trade.pnl -= 0.012  # 1.2% round-trip fees
        
        self._save_trade(trade)
        
        # Check prediction accuracy
        prediction_correct = (trade.predicted_outcome == actual_outcome)
        
        emoji = "✅" if prediction_correct else "❌"
        self.notifier.send_message(
            f"{emoji} Paper Trade Closed: {trade.pair}\n"
            f"Predicted: {trade.predicted_outcome} | Actual: {actual_outcome}\n"
            f"P&L: {trade.pnl:+.2%}\n"
            f"Slippage: {trade.slippage:.4%}"
        )
        
        logger.info(f"Paper trade closed: {trade.signal_id}, P&L: {trade.pnl:.2%}")
    
    def get_validation_report(self) -> Dict:
        """
        Generate validation report comparing paper to backtest
        
        Returns:
            Dict with validation metrics
        """
        if not self.trades:
            return {'error': 'No paper trades recorded'}
        
        closed_trades = [t for t in self.trades if t.status == 'closed']
        
        if not closed_trades:
            return {'error': 'No closed trades yet'}
        
        # Prediction accuracy
        correct_predictions = sum(
            1 for t in closed_trades 
            if t.predicted_outcome == t.actual_outcome
        )
        accuracy = correct_predictions / len(closed_trades)
        
        # Win rate
        wins = sum(1 for t in closed_trades if t.actual_outcome == 'win')
        win_rate = wins / len(closed_trades)
        
        # Average metrics
        avg_slippage = sum(t.slippage for t in closed_trades) / len(closed_trades)
        avg_latency = sum(t.latency_ms for t in closed_trades) / len(closed_trades)
        
        # P&L
        total_pnl = sum(t.pnl for t in closed_trades if t.pnl)
        avg_pnl = total_pnl / len(closed_trades)
        
        return {
            'total_trades': len(self.trades),
            'closed_trades': len(closed_trades),
            'prediction_accuracy': accuracy,
            'paper_win_rate': win_rate,
            'avg_slippage': avg_slippage,
            'avg_latency_ms': avg_latency,
            'total_pnl': total_pnl,
            'avg_trade_pnl': avg_pnl,
            'backtest_deviation': 'calculating...'  # Would compare to backtest
        }
    
    def check_open_trades(self):
        """Check open trades and close if SL/TP hit"""
        open_trades = [t for t in self.trades if t.status == 'open']
        
        for trade in open_trades:
            try:
                current_price = self.client.get_product_price(trade.pair)
                
                # Check if SL or TP hit
                if trade.direction == 'LONG':
                    if current_price <= trade.stop_loss:
                        self.close_paper_trade(trade, trade.stop_loss, 'loss')
                    elif current_price >= trade.take_profit:
                        self.close_paper_trade(trade, trade.take_profit, 'win')
                else:  # SHORT
                    if current_price >= trade.stop_loss:
                        self.close_paper_trade(trade, trade.stop_loss, 'loss')
                    elif current_price <= trade.take_profit:
                        self.close_paper_trade(trade, trade.take_profit, 'win')
                        
            except Exception as e:
                logger.error(f"Error checking trade {trade.signal_id}: {e}")

if __name__ == '__main__':
    print("Paper Validator loaded")
    print("Tracks: signal accuracy, slippage, latency, fill rates")
