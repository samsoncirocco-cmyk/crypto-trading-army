#!/usr/bin/env python3
"""
Advanced Risk Metrics - Sharpe, Sortino, Calmar ratios
"""
import math
import statistics
from datetime import datetime, timedelta

def calculate_sharpe_ratio(returns, risk_free_rate=0.02):
    """
    Calculate Sharpe Ratio
    returns: list of daily returns (as decimals, e.g., 0.01 for 1%)
    risk_free_rate: annual risk-free rate (default 2%)
    """
    if len(returns) < 2:
        return 0
    
    # Convert annual risk-free to daily
    daily_rf = risk_free_rate / 365
    
    excess_returns = [r - daily_rf for r in returns]
    
    avg_excess = statistics.mean(excess_returns)
    std_excess = statistics.stdev(excess_returns) if len(excess_returns) > 1 else 0
    
    if std_excess == 0:
        return 0
    
    # Annualize
    sharpe = (avg_excess / std_excess) * math.sqrt(365)
    return sharpe

def calculate_sortino_ratio(returns, risk_free_rate=0.02):
    """
    Calculate Sortino Ratio (downside deviation only)
    """
    if len(returns) < 2:
        return 0
    
    daily_rf = risk_free_rate / 365
    excess_returns = [r - daily_rf for r in returns]
    avg_excess = statistics.mean(excess_returns)
    
    # Downside deviation (only negative returns)
    downside_returns = [r for r in excess_returns if r < 0]
    if not downside_returns:
        return float('inf')  # No downside
    
    downside_std = math.sqrt(sum(r**2 for r in downside_returns) / len(downside_returns))
    
    if downside_std == 0:
        return 0
    
    sortino = (avg_excess / downside_std) * math.sqrt(365)
    return sortino

def calculate_calmar_ratio(returns, max_drawdown):
    """
    Calculate Calmar Ratio (return / max drawdown)
    """
    if max_drawdown == 0:
        return 0
    
    annual_return = statistics.mean(returns) * 365
    calmar = annual_return / abs(max_drawdown)
    return calmar

def calculate_max_drawdown(equity_curve):
    """
    Calculate maximum drawdown from equity curve
    """
    max_dd = 0
    peak = equity_curve[0]
    
    for value in equity_curve:
        if value > peak:
            peak = value
        dd = (peak - value) / peak
        max_dd = max(max_dd, dd)
    
    return max_dd

def calculate_var(returns, confidence=0.95):
    """
    Calculate Value at Risk (VaR)
    """
    if not returns:
        return 0
    
    sorted_returns = sorted(returns)
    index = int((1 - confidence) * len(sorted_returns))
    return sorted