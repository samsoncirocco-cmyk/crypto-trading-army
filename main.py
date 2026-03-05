#!/usr/bin/env python3
"""
Coinbase Trading Bot - CLI Entry Point
Real cash account support with paper mode default and safety locks.

Usage:
    python main.py portfolio              # Show current balances & positions
    python main.py buy BTC-USD 5.00      # Buy $5 of BTC (paper mode by default)
    python main.py sell BTC-USD 0.0001   # Sell 0.0001 BTC
    python main.py status                # Show risk limits and daily stats
    python main.py price BTC-USD         # Get current price
    python main.py halt                  # Emergency halt all trading
    python main.py resume                # Resume after halt

Set PAPER_MODE=false in .env to enable live trading.
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Load .env from this directory
load_dotenv(Path(__file__).parent / '.env')

sys.path.insert(0, str(Path(__file__).parent))

from coinbase_advanced import CoinbaseAdvancedClient, CoinbaseAPIError
from portfolio import PortfolioTracker
from risk import RiskManager, RiskViolation, TradingHaltedError


def get_client():
    try:
        return CoinbaseAdvancedClient()
    except ValueError as e:
        print(f"❌ Config error: {e}")
        sys.exit(1)


def cmd_portfolio(args):
    """Show portfolio summary"""
    client = get_client()
    tracker = PortfolioTracker(client)
    print(tracker.get_daily_summary())


def cmd_price(args):
    """Get current market price"""
    client = get_client()
    pair = args.pair.upper()
    try:
        price = client.get_product_price(pair)
        print(f"💰 {pair}: ${price:,.2f}")
    except CoinbaseAPIError as e:
        print(f"❌ API error: {e}")


def cmd_buy(args):
    """Execute a buy order"""
    client = get_client()
    risk = RiskManager()

    pair = args.pair.upper()
    amount = args.amount

    try:
        risk.validate_order(pair, amount, 'BUY')

        tracker = PortfolioTracker(client)
        if not tracker.can_trade(amount):
            print(f"❌ Insufficient USD balance for ${amount:.2f}")
            return

        if not client.live_mode:
            price = client.get_product_price(pair)
            asset = pair.split('-')[0]
            qty = amount / price if price else 0
            print(f"📋 PAPER MODE: Would buy ${amount:.2f} of {pair}")
            print(f"   ≈ {qty:.8f} {asset} @ ${price:,.2f}")
            print(f"   Set PAPER_MODE=false in .env for live trading")
            return

        if not args.yes:
            confirm = input(f"⚠️  LIVE: Buy ${amount:.2f} of {pair} with real money? (yes/no): ")
            if confirm.lower() != 'yes':
                print("Cancelled")
                return

        print(f"🚀 Placing market buy: ${amount:.2f} of {pair}")
        order = client.place_market_buy(pair, amount)

        if order:
            risk.record_order(pair, amount, 'BUY')
            print(f"✅ Order placed: {order.order_id}")

    except RiskViolation as e:
        print(f"❌ Risk check failed: {e}")
    except CoinbaseAPIError as e:
        print(f"❌ API error: {e}")
    except TradingHaltedError as e:
        print(f"🛑 {e}")


def cmd_sell(args):
    """Execute a sell order (amount is in base asset, e.g. BTC quantity)"""
    client = get_client()
    risk = RiskManager()

    pair = args.pair.upper()
    base_size = args.amount   # e.g. 0.001 BTC

    try:
        # For sells, validate against approximate USD value
        price = client.get_product_price(pair)
        approx_usd = base_size * price if price else 0

        risk.validate_order(pair, approx_usd, 'SELL')

        asset = pair.split('-')[0]

        if not client.live_mode:
            print(f"📋 PAPER MODE: Would sell {base_size:.8f} {asset}")
            print(f"   ≈ ${approx_usd:,.2f} @ ${price:,.2f}")
            print(f"   Set PAPER_MODE=false in .env for live trading")
            return

        if not args.yes:
            confirm = input(
                f"⚠️  LIVE: Sell {base_size:.8f} {asset} (≈${approx_usd:,.2f})? (yes/no): "
            )
            if confirm.lower() != 'yes':
                print("Cancelled")
                return

        print(f"🚀 Placing market sell: {base_size:.8f} {asset}")
        order = client.place_market_sell(pair, base_size)

        if order:
            risk.record_order(pair, approx_usd, 'SELL')
            print(f"✅ Order placed: {order.order_id}")

    except RiskViolation as e:
        print(f"❌ Risk check failed: {e}")
    except CoinbaseAPIError as e:
        print(f"❌ API error: {e}")
    except TradingHaltedError as e:
        print(f"🛑 {e}")


def cmd_status(args):
    """Show risk status and daily limits"""
    risk = RiskManager()
    s = risk.get_status()

    mode_str = "🔴 LIVE" if os.getenv('PAPER_MODE', 'true').lower() == 'false' else "📋 PAPER"

    print("🛡️  Risk Status")
    print(f"   Mode:             {mode_str}")
    print(f"   Trading allowed:  {'✅ Yes' if s['trading_allowed'] else '🛑 HALTED'}")
    print(f"   Daily spent:      ${s['daily_spent']:.2f} / ${risk.MAX_DAILY_BUDGET:.2f}")
    print(f"   Daily remaining:  ${s['daily_remaining']:.2f}")
    print(f"   Daily P&L:        ${s['daily_pnl']:+.2f}")
    print(f"   Orders today:     {s['orders_today']}")
    print()
    print("📏 Hard Limits (cannot be changed in code):")
    print(f"   Max order size:   ${risk.MAX_ORDER_SIZE:.2f}")
    print(f"   Max daily spend:  ${risk.MAX_DAILY_BUDGET:.2f}")
    print(f"   Max capital:      ${risk.MAX_TOTAL_CAPITAL:.2f}")
    print(f"   Daily loss limit: ${risk.DAILY_LOSS_LIMIT:.2f}")
    print(f"   Allowed pairs:    {', '.join(risk.ALLOWED_PAIRS)}")


def cmd_halt(args):
    """Emergency halt all trading"""
    risk = RiskManager.__new__(RiskManager)  # Skip halt check in __init__
    risk.DATA_DIR = Path(__file__).parent / 'data'
    risk.DATA_DIR.mkdir(exist_ok=True)
    reason = args.reason or "Manual halt via CLI"
    halt_file = risk.DATA_DIR / 'HALT'
    halt_file.write_text(f"{reason}\n")
    print(f"🛑 Trading HALTED: {reason}")
    print(f"   Run `python main.py resume` to re-enable")


def cmd_resume(args):
    """Resume trading after a halt"""
    halt_file = Path(__file__).parent / 'data' / 'HALT'
    if halt_file.exists():
        halt_file.unlink()
        print("✅ Trading resumed")
    else:
        print("ℹ️  Trading was not halted")


def cmd_strategy(args):
    """Run DCA strategy once"""
    from strategy import DCAStrategy
    
    pair = args.pair.upper()
    amount = args.amount
    
    print(f"🔄 Running DCA strategy: ${amount} of {pair}")
    
    try:
        strategy = DCAStrategy()
        result = strategy.execute_dca_buy(pair, amount)
        
        if result.success:
            print(f"✅ DCA buy successful!")
            print(f"   Order ID: {result.order_id}")
            print(f"   Amount: ${result.amount:.2f}")
            if result.price:
                print(f"   Price: ${result.price:,.2f}")
        else:
            print(f"❌ DCA failed: {result.error}")
            
    except Exception as e:
        print(f"❌ Error: {e}")


def cmd_daemon(args):
    """Start background scheduler daemon"""
    from scheduler import TradingScheduler
    
    scheduler = TradingScheduler()
    
    if args.once:
        print("🔄 Running one-time DCA...")
        scheduler.run_once(args.pair, args.amount)
    else:
        print(f"🤖 Starting daemon (interval: {args.interval}min)...")
        print("   Press Ctrl+C to stop")
        scheduler.run(args.interval)


def main():
    parser = argparse.ArgumentParser(
        description='Coinbase Trading Bot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    sub = parser.add_subparsers(dest='command')

    # portfolio
    sub.add_parser('portfolio', help='Show portfolio summary')

    # price
    p_price = sub.add_parser('price', help='Get current price')
    p_price.add_argument('pair', help='Trading pair (e.g. BTC-USD)')

    # buy
    p_buy = sub.add_parser('buy', help='Buy crypto')
    p_buy.add_argument('pair', help='Trading pair (e.g. BTC-USD)')
    p_buy.add_argument('amount', type=float, help='USD amount to spend')
    p_buy.add_argument('-y', '--yes', action='store_true', help='Skip confirmation')

    # sell
    p_sell = sub.add_parser('sell', help='Sell crypto (amount in base asset)')
    p_sell.add_argument('pair', help='Trading pair (e.g. BTC-USD)')
    p_sell.add_argument('amount', type=float, help='Base asset quantity to sell (e.g. 0.001 BTC)')
    p_sell.add_argument('-y', '--yes', action='store_true', help='Skip confirmation')

    # status
    sub.add_parser('status', help='Show risk limits and daily stats')

    # halt
    p_halt = sub.add_parser('halt', help='Emergency halt all trading')
    p_halt.add_argument('--reason', default=None, help='Halt reason')

    # resume
    sub.add_parser('resume', help='Resume trading after halt')
    
    # strategy
    p_strategy = sub.add_parser('strategy', help='Run DCA strategy once')
    p_strategy.add_argument('--pair', default='BTC-USD',
                            help='Trading pair (default: BTC-USD)')
    p_strategy.add_argument('--amount', type=float, default=5.0,
                            help='USD amount (default: 5.0)')
    p_strategy.set_defaults(func=cmd_strategy)
    
    # daemon
    p_daemon = sub.add_parser('daemon', help='Start background scheduler')
    p_daemon.add_argument('--interval', type=int, default=60,
                          help='Check interval in minutes (default: 60)')
    p_daemon.add_argument('--once', action='store_true',
                          help='Run once and exit (for cron)')
    p_daemon.add_argument('--pair', default='BTC-USD',
                          help='Trading pair (default: BTC-USD)')
    p_daemon.add_argument('--amount', type=float, default=5.0,
                          help='DCA amount in USD (default: 5.0)')
    p_daemon.set_defaults(func=cmd_daemon)

    args = parser.parse_args()

    dispatch = {
        'portfolio': cmd_portfolio,
        'price':     cmd_price,
        'buy':       cmd_buy,
        'sell':      cmd_sell,
        'status':    cmd_status,
        'halt':      cmd_halt,
        'resume':    cmd_resume,
        'strategy':  cmd_strategy,
        'daemon':    cmd_daemon,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
