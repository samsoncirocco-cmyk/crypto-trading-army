#!/usr/bin/env python3
"""
Adjusted Backtest - Tuned parameters + Multi-Agent Army Setup
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

from liquidity_sweep_engine import LiquiditySweepEngine, TradeDirection
from backtest_engine import BacktestEngine

def load_sol_data():
    """Load SOL 1-minute data from 392 pairs dataset"""
    logger.info("📊 Loading SOL 1-minute data...")
    
    # Find SOL file in 392 pairs dataset
    sol_path = None
    base_path = Path.home() / '.cache/kagglehub/datasets/tencars/392-crypto-currency-pairs-at-minute-resolution/versions/1231'
    
    for file in base_path.glob('sol*.csv'):
        if 'usd' in file.name.lower():
            sol_path = file
            break
    
    if not sol_path:
        # Use BTC as fallback
        logger.warning("SOL not found, using BTC as proxy...")
        return load_btc_data()
    
    df = pd.read_csv(sol_path)
    df['timestamp'] = pd.to_datetime(df['date'])
    df = df.set_index('timestamp')
    df = df.rename(columns={
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'volume': 'volume'
    })
    
    # Use last 6 months
    cutoff = df.index.max() - pd.Timedelta(days=180)
    df = df[df.index >= cutoff]
    
    logger.info(f"✅ Loaded {len(df):,} SOL 1-minute candles")
    return df

def load_btc_data():
    """Load BTC 1-minute data"""
    logger.info("📊 Loading BTC 1-minute data...")
    
    btc_path = Path.home() / '.cache/kagglehub/datasets/mczielinski/bitcoin-historical-data/versions/524/btcusd_1-min_data.csv'
    
    df = pd.read_csv(btc_path)
    df['timestamp'] = pd.to_datetime(df['Timestamp'], unit='s')
    df = df.set_index('timestamp')
    df = df.rename(columns={
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Close': 'close',
        'Volume': 'volume'
    })
    
    cutoff = df.index.max() - pd.Timedelta(days=180)
    df = df[df.index >= cutoff]
    
    logger.info(f"✅ Loaded {len(df):,} BTC 1-minute candles")
    return df

def run_backtest_for_asset(asset_name, df_1m):
    """Run backtest for a specific asset"""
    logger.info(f"\n{'='*50}")
    logger.info(f"🔍 Testing {asset_name}")
    logger.info(f"{'='*50}")
    
    # Create timeframes
    df_5m = df_1m.resample('5min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    df_15m = df_1m.resample('15min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    # ADJUSTED PARAMETERS (TUNED)
    sweep_engine = LiquiditySweepEngine(
        sweep_lookback=15,          # Shorter lookback = more signals
        min_sweep_wick_ratio=1.8,   # Easier sweep detection
        volume_threshold=1.3,       # Lower volume threshold
        sl_percent=0.02,            # 2.0% stop loss (was 1.2%)
        tp_percent=0.04             # 4.0% target (was 2.4%) - Better RR
    )
    
    backtest_engine = BacktestEngine(
        engine=sweep_engine,
        initial_capital=10000.0,
        risk_per_trade=0.02,
        coinbase_fee=0.006
    )
    
    # Detect signals
    signals = sweep_engine.detect_sweeps(df_1m, df_5m, df_15m, asset_name)
    
    if not signals:
        logger.warning(f"No signals for {asset_name}")
        return None
    
    # Filter to max 3 per day
    daily_counts = {}
    filtered_signals = []
    for sig in signals:
        day = sig.timestamp.date()
        if daily_counts.get(day, 0) < 3:
            filtered_signals.append(sig)
            daily_counts[day] = daily_counts.get(day, 0) + 1
    
    logger.info(f"Found {len(signals)} sweeps, filtered to {len(filtered_signals)} trades")
    
    # Run backtest
    result = backtest_engine.run_backtest(filtered_signals, df_1m)
    mc_results = backtest_engine.monte_carlo_simulation(result, n_simulations=1000)
    
    return {
        'asset': asset_name,
        'signals': len(filtered_signals),
        'trades': result.total_trades,
        'win_rate': result.win_rate,
        'profit_factor': result.profit_factor,
        'return': result.total_return,
        'max_dd': result.max_drawdown,
        'sharpe': result.sharpe_ratio,
        'mc_prob_profit': mc_results.get('prob_profit', 0),
        'mc_worst_case': mc_results.get('worst_case_equity', 0)
    }

def format_results(results):
    """Format multi-asset results"""
    output = []
    output.append("\n" + "="*70)
    output.append("🚀 ADJUSTED PARAMETERS - MULTI-AGENT BACKTEST RESULTS")
    output.append("="*70)
    output.append("\n📊 PARAMETER CHANGES:")
    output.append("   Stop Loss:    1.2% → 2.0% (gives more room)")
    output.append("   Take Profit:  2.4% → 4.0% (better RR ratio)")
    output.append("   Lookback:     20 → 15 bars (more signals)")
    output.append("   Wick Ratio:   2.0 → 1.8 (easier sweeps)")
    output.append("   Volume Thres: 1.5 → 1.3 (more opportunities)")
    
    output.append("\n📈 RESULTS BY ASSET:")
    output.append("-" * 70)
    output.append(f"{'Asset':<8} {'Trades':<8} {'Win%':<8} {'Profit':<10} {'PF':<6} {'Sharpe':<8} {'Safe?':<6}")
    output.append("-" * 70)
    
    total_trades = 0
    for r in results:
        if r:
            total_trades += r['trades']
            safe = "✅" if r['mc_prob_profit'] > 0.8 else "⚠️"
            output.append(f"{r['asset']:<8} {r['trades']:<8} {r['win_rate']:.1%}    {r['return']:+.1%}      {r['profit_factor']:.2f}   {r['sharpe']:.2f}    {safe}")
    
    output.append("-" * 70)
    output.append(f"TOTAL TRADES: {total_trades}")
    
    output.append("\n📝 PLAIN ENGLISH:")
    if total_trades >= 20:
        output.append("✅ Good trade frequency - hitting 2+ trades/day target")
    else:
        output.append("⚠️ Still low trade count - may need more assets or looser filters")
    
    best_pf = max([r['profit_factor'] for r in results if r], default=0)
    if best_pf >= 2.0:
        output.append(f"✅ Profit Factor {best_pf:.2f} - winners are 2x+ losers")
    else:
        output.append(f"⚠️ Profit Factor {best_pf:.2f} - still below 2.0 target")
    
    output.append("\n" + "="*70)
    return "\n".join(output)

if __name__ == '__main__':
    results = []
    
    # Test BTC
    btc_data = load_btc_data()
    if btc_data is not None:
        btc_result = run_backtest_for_asset("BTC-USD", btc_data)
        if btc_result:
            results.append(btc_result)
    
    # Test SOL
    try:
        sol_data = load_sol_data()
        if sol_data is not None:
            sol_result = run_backtest_for_asset("SOL-USD", sol_data)
            if sol_result:
                results.append(sol_result)
    except Exception as e:
        logger.error(f"SOL test failed: {e}")
    
    print(format_results(results))
    
    # Save results
    with open('adjusted_backtest_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    logger.info("\n💾 Results saved to adjusted_backtest_results.json")
