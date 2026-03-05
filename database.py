#!/usr/bin/env python3
"""
Database Module - SQLite for trade analytics
"""
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

class TradeDatabase:
    def __init__(self, db_path='trading.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Trades table
        c.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE,
                timestamp TEXT,
                asset TEXT,
                direction TEXT,
                entry_price REAL,
                exit_price REAL,
                position_size_usd REAL,
                pnl_usd REAL,
                pnl_pct REAL,
                status TEXT,
                paper_mode INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Signals table
        c.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id TEXT,
                timestamp TEXT,
                agent_id TEXT,
                asset TEXT,
                direction TEXT,
                confidence REAL,
                entry_price REAL,
                source TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Performance metrics table
        c.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE,
                total_trades INTEGER,
                win_rate REAL,
                profit_factor REAL,
                sharpe_ratio REAL,
                max_drawdown REAL,
                total_pnl REAL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_trade(self, trade_data):
        """Save trade to database"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            INSERT OR REPLACE INTO trades 
            (trade_id, timestamp, asset, direction, entry_price, exit_price,
             position_size_usd, pnl_usd, pnl_pct, status, paper_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_data.get('trade_id'),
            trade_data.get('timestamp'),
            trade_data.get('asset'),
            trade_data.get('direction'),
            trade_data.get('entry_price'),
            trade_data.get('exit_price'),
            trade_data.get('position_size_usd'),
            trade_data.get('pnl_usd'),
            trade_data.get('pnl_pct'),
            trade_data.get('status'),
            1 if trade_data.get('paper_mode') else 0
        ))
        
        conn.commit()
        conn.close()
    
    def get_daily_stats(self, date):
        """Get stats for specific date"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT COUNT(*), SUM(pnl_usd), AVG(pnl_usd)
            FROM trades
            WHERE DATE(timestamp) = ? AND status = 'CLOSED'
        ''', (date,))
        
        result = c.fetchone()
        conn.close()
        
        return {
            'trades': result[0] or 0,
            'total_pnl': result[1] or 0,
            'avg_pnl': result[2] or 0
        }
    
    def get_all_stats(self):
        """Get all-time stats"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl_usd < 0 THEN 1 ELSE 0 END) as losses,
                SUM(pnl_usd) as total_pnl,
                AVG(pnl_usd) as avg_pnl
            FROM trades
            WHERE status = 'CLOSED'
        ''')
        
        result = c.fetchone()
        conn.close()
        
        total = result[0] or 0
        wins = result[1] or 0
        
        return {
            'total_trades': total,
            'wins': wins,
            'losses': result[2] or 0,
            'win_rate': wins / total if total > 0 else 0,
            'total_pnl': result[3] or 0,
            'avg_pnl': result[4] or 0
        }

if __name__ == '__main__':
    db = TradeDatabase()
    print("✅ Database initialized")
    
    # Test save
    test_trade = {
        'trade_id': 'test_001',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'asset': 'BTC-USD',
        'direction': 'LONG',
        'entry_price': 66519,
        'exit_price': 67000,
        'position_size_usd': 10,
        'pnl_usd': 0.72,
        'pnl_pct': 7.2,
