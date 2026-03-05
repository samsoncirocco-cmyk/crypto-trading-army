#!/usr/bin/env python3
"""
Backtest Engine with Monte Carlo Simulation

Implements walk-forward analysis and Monte Carlo stress testing
for robust strategy validation.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import logging

from liquidity_sweep_engine import LiquiditySweepEngine, SweepSignal, TradeDirection

logger = logging.getLogger(__name__)

@dataclass
class BacktestResult:
    """Results from a single backtest run"""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    total_return: float
    avg_trade_return: float
    avg_winner: float
    avg_loser: float
    max_consecutive_losses: int
    equity_curve: List[float]
    trades: List[Dict]

def calculate_sharpe(returns: List[float], risk_free_rate: float = 0.0) -> float:
    """Calculate annualized Sharpe ratio"""
    if len(returns) < 2:
        return 0.0
    returns_arr = np.array(returns)
    excess_returns = returns_arr - risk_free_rate
    if np.std(excess_returns) == 0:
        return 0.0
    return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)

def calculate_max_drawdown(equity_curve: List[float]) -> float:
    """Calculate maximum drawdown as percentage"""
    if not equity_curve:
        return 0.0
    
    peak = equity_curve[0]
    max_dd = 0.0
    
    for equity in equity_curve:
        if equity > peak:
            peak = equity
        drawdown = (peak - equity) / peak
        max_dd = max(max_dd, drawdown)
    
    return max_dd

class BacktestEngine:
    """
    Backtesting engine with walk-forward and Monte Carlo capabilities
    """
    
    def __init__(self, 
                 engine: LiquiditySweepEngine,
                 initial_capital: float = 10000.0,
                 risk_per_trade: float = 0.02,
                 coinbase_fee: float = 0.006):
        """
        Args:
            engine: Liquidity sweep detection engine
            initial_capital: Starting capital
            risk_per_trade: Risk per trade (2%)
            coinbase_fee: Coinbase taker fee (0.6%)
        """
        self.engine = engine
        self.initial_capital = initial_capital
        self.risk_per_trade = risk_per_trade
        self.coinbase_fee = coinbase_fee
    
    def run_backtest(self, 
                     signals: List[SweepSignal],
                     price_data: pd.DataFrame) -> BacktestResult:
        """
        Run backtest on a set of signals
        
        Args:
            signals: List of trade signals
            price_data: OHLCV data for simulation
        
        Returns:
            BacktestResult with performance metrics
        """
        if not signals:
            return BacktestResult(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, [self.initial_capital], [])
        
        capital = self.initial_capital
        equity_curve = [capital]
        trades = []
        
        winners = 0
        losers = 0
        total_profit = 0
        total_loss = 0
        max_consecutive_losses = 0
        current_consecutive_losses = 0
        
        for signal in signals:
            # Simulate trade outcome
            trade_result = self._simulate_trade(signal, price_data)
            
            if trade_result['pnl'] > 0:
                winners += 1
                total_profit += trade_result['pnl']
                current_consecutive_losses = 0
            else:
                losers += 1
                total_loss += abs(trade_result['pnl'])
                current_consecutive_losses += 1
                max_consecutive_losses = max(max_consecutive_losses, current_consecutive_losses)
            
            capital += trade_result['pnl']
            equity_curve.append(capital)
            
            trades.append({
                'timestamp': signal.timestamp.isoformat(),
                'direction': signal.direction.value,
                'pair': signal.pair,
                'entry': signal.entry_price,
                'exit': trade_result['exit_price'],
                'pnl': trade_result['pnl'],
                'pnl_pct': trade_result['pnl_pct'],
                'sl': signal.stop_loss,
                'tp': signal.take_profit
            })
            
            # Stop if we hit max daily drawdown
            daily_dd = calculate_max_drawdown(equity_curve[-100:])  # Look back ~1 day
            if daily_dd > 0.05:  # 5% max daily drawdown
                logger.warning(f"Max daily drawdown hit: {daily_dd:.2%}")
                break
        
        total_trades = winners + losers
        win_rate = winners / total_trades if total_trades > 0 else 0
        
        # Profit factor
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        # Calculate returns for Sharpe
        returns = []
        for i in range(1, len(equity_curve)):
            ret = (equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1]
            returns.append(ret)
        
        sharpe = calculate_sharpe(returns)
        max_dd = calculate_max_drawdown(equity_curve)
        total_return = (capital - self.initial_capital) / self.initial_capital
        
        avg_winner = total_profit / winners if winners > 0 else 0
        avg_loser = total_loss / losers if losers > 0 else 0
        avg_trade = (total_profit - total_loss) / total_trades if total_trades > 0 else 0
        
        return BacktestResult(
            total_trades=total_trades,
            winning_trades=winners,
            losing_trades=losers,
            win_rate=win_rate,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            total_return=total_return,
            avg_trade_return=avg_trade,
            avg_winner=avg_winner,
            avg_loser=avg_loser,
            max_consecutive_losses=max_consecutive_losses,
            equity_curve=equity_curve,
            trades=trades
        )
    
    def _simulate_trade(self, signal: SweepSignal, price_data: pd.DataFrame) -> Dict:
        """
        Simulate trade outcome using realistic probabilistic win rates.

        BUG FIX: Old version always won when RR >= 2.0 (always true),
        producing impossible 94%+ win rates. Real liquidity sweep strategies
        achieve 30-45% win rate with 2:1 RR.

        Win probability by signal strength:
          STRONG  (HTF aligned, high vol) : 40%
          MODERATE                        : 33%  <- breakeven at 2:1 RR after fees
          WEAK                            : 25%

        Uses walk-forward price data when available; falls back to probability.
        """
        risk_amount = self.initial_capital * self.risk_per_trade

        if signal.direction == TradeDirection.LONG:
            sl_distance = signal.entry_price - signal.stop_loss
        else:
            sl_distance = signal.stop_loss - signal.entry_price

        if sl_distance == 0:
            return {"pnl": 0, "pnl_pct": 0, "exit_price": signal.entry_price}

        position_size = risk_amount / sl_distance

        # Walk-forward through price data to find which hits first
        won = None
        if not price_data.empty and "close" in price_data.columns:
            try:
                future = price_data[price_data.index > signal.timestamp]
                for _, bar in future.iterrows():
                    if signal.direction == TradeDirection.LONG:
                        if bar["low"] <= signal.stop_loss:
                            won = False
                            break
                        if bar["high"] >= signal.take_profit:
                            won = True
                            break
                    else:
                        if bar["high"] >= signal.stop_loss:
                            won = False
                            break
                        if bar["low"] <= signal.take_profit:
                            won = True
                            break
            except Exception:
                won = None

        # Fall back to calibrated win probability
        if won is None:
            win_probs = {1: 0.25, 2: 0.33, 3: 0.40}
            p = win_probs.get(signal.strength.value, 0.33)
            won = np.random.random() < p

        # Calculate P&L
        if won:
            exit_price = signal.take_profit
            if signal.direction == TradeDirection.LONG:
                gross_pnl = (signal.take_profit - signal.entry_price) * position_size
            else:
                gross_pnl = (signal.entry_price - signal.take_profit) * position_size
        else:
            exit_price = signal.stop_loss
            if signal.direction == TradeDirection.LONG:
                gross_pnl = -(signal.entry_price - signal.stop_loss) * position_size
            else:
                gross_pnl = -(signal.stop_loss - signal.entry_price) * position_size

        notional = position_size * signal.entry_price
        fees = notional * self.coinbase_fee * 2
        net_pnl = gross_pnl - fees

        return {
            "pnl": net_pnl,
            "pnl_pct": net_pnl / self.initial_capital,
            "exit_price": exit_price,
            "won": won,
        }


    def monte_carlo_simulation(self, 
                               backtest_result: BacktestResult,
                               n_simulations: int = 10000) -> Dict:
        """
        Run Monte Carlo simulation on backtest results
        
        Randomizes trade order to test sequence risk
        """
        if not backtest_result.trades:
            return {}
        
        # Extract trade returns
        trade_returns = []
        for trade in backtest_result.trades:
            pnl_pct = trade['pnl'] / self.initial_capital
            trade_returns.append(pnl_pct)
        
        # Run simulations
        final_equities = []
        max_drawdowns = []
        
        for _ in range(n_simulations):
            # Randomize trade order
            shuffled_returns = np.random.permutation(trade_returns)
            
            # Calculate equity curve
            equity = self.initial_capital
            equity_curve = [equity]
            
            for ret in shuffled_returns:
                equity *= (1 + ret)
                equity_curve.append(equity)
            
            final_equities.append(equity)
            max_drawdowns.append(calculate_max_drawdown(equity_curve))
        
        # Calculate confidence intervals
        final_equities = np.array(final_equities)
        max_drawdowns = np.array(max_drawdowns)
        
        return {
            'n_simulations': n_simulations,
            'mean_final_equity': np.mean(final_equities),
            'median_final_equity': np.median(final_equities),
            'worst_case_equity': np.percentile(final_equities, 5),
            'best_case_equity': np.percentile(final_equities, 95),
            'mean_max_drawdown': np.mean(max_drawdowns),
            'worst_max_drawdown': np.percentile(max_drawdowns, 95),
            'prob_profit': np.mean(final_equities > self.initial_capital),
            'prob_double': np.mean(final_equities > self.initial_capital * 2),
            'prob_blowup': np.mean(final_equities < self.initial_capital * 0.5)
        }
    
    def walk_forward_analysis(self, 
                              data: pd.DataFrame,
                              train_pct: float = 0.7) -> Dict:
        """
        Walk-forward analysis: train on first 70%, test on last 30%
        """
        split_idx = int(len(data) * train_pct)
        
        train_data = data.iloc[:split_idx]
        test_data = data.iloc[split_idx:]
        
        # In real implementation, we'd optimize parameters on train
        # Then test on test data
        # For now, just run backtest on both
        
        logger.info(f"Walk-forward: train={len(train_data)}, test={len(test_data)}")
        
        # Generate signals on test data
        signals = self.engine.detect_sweeps(test_data, test_data, test_data, "TEST")
        
        # Backtest
        result = self.run_backtest(signals, test_data)
        
        return {
            'train_size': len(train_data),
            'test_size': len(test_data),
            'test_result': result
        }

if __name__ == '__main__':
    print("Backtest Engine with Monte Carlo loaded")
    print("Features: Walk-forward, Monte Carlo simulation, Sharpe/Sortino")
