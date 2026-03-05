#!/usr/bin/env python3
"""
Web Dashboard - Real-time trading monitor
Serves on localhost:8080
"""
import os, json
from datetime import datetime, timezone
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

PORT = 8080
BASE_DIR = Path(__file__).parent

class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress logs
    
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(self.get_dashboard_html().encode())
        elif self.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(self.get_status()).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def get_status(self):
        """Get current trading status"""
        # Count signals
        signal_dir = BASE_DIR / 'data' / 'signals'
        signals = len(list(signal_dir.glob('*.json'))) if signal_dir.exists() else 0
        
        # Count trades
        trades_dir = BASE_DIR / 'data' / 'trades'
        trades = len(list(trades_dir.glob('*.json'))) if trades_dir.exists() else 0
        
        # Paper mode
        paper = os.getenv('PAPER_MODE', 'true').lower() == 'true'
        
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'paper_mode': paper,
            'signals': signals,
            'trades': trades,
            'mode': 'PAPER' if paper else 'LIVE'
        }
    
    def get_dashboard_html(self):
        return '''<!DOCTYPE html>
<html>
<head>
    <title>Crypto God John - Dashboard</title>
    <meta http-equiv="refresh" content="10">
    <style>
        body { font-family: monospace; background: #0a0a0a; color: #00ff00; padding: 20px; }
        h1 { color: #00ff00; border-bottom: 2px solid #00ff00; }
        .metric { background: #111; padding: 15px; margin: 10px 0; border-left: 3px solid #00ff00; }
        .metric h3 { margin: 0 0 10px 0; color: #fff; }
        .value { font-size: 24px; color: #00ff00; }
        .status-paper { color: #ffff00; }
        .status-live { color: #ff0000; font-weight: bold; }
        .refresh { color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <h1>🤖 CRYPTO GOD JOHN</h1>
    <p class="refresh">Auto-refreshes every 10 seconds</p>
    
    <div class="metric">
        <h3>Mode</h3>
        <div class="value status-''' + ('paper">📋 PAPER (Safe)' if os.getenv('PAPER_MODE','true').lower()=='true' else 'live">💰 LIVE (Real Money)') + '''</div>
    </div>
    
    <div class="metric">
        <h3>Signals Generated</h3>
        <div class="value">''' + str(self.get_status()['signals']) + '''</div>
    </div>
    
    <div class="metric">
        <h3>Trades Executed</h3>
        <div class="value">''' + str(self.get_status()['trades']) + '''</div>
    </div>
    
    <div class="metric">
        <h3>Safety Limits</h3>
        <div>Max 3 trades/day | Max $10/position | $5 daily loss halt</div>
    </div>
    
    <div class="metric">
        <h3>Commands</h3>
        <code>./quick-start.sh</code> - Start trading<br>
        <code>./EMERGENCY_HALT.sh</code> - Stop all trading<br>
        <code>python3 status.py</code> - View status
    </div>
</body>
</html>'''

def run_server():
    server = HTTPServer(('localhost', PORT), DashboardHandler)
    print(f"🌐 Dashboard running at http://localhost:{PORT}")
    server.serve_forever()

if __name__ == '__main__':
    run_server()
