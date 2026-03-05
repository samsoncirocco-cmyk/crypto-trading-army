#!/usr/bin/env python3
"""
SUPERVISOR - Master process for trading agent army
Starts all agents, monitors health, auto-restarts on crash
"""
import subprocess, time, signal, sys, os
from pathlib import Path
from datetime import datetime

AGENTS = [
    # Live scouts with real Coinbase feeds
    ("btc_scout", "agents/btc_scout_live.py"),
    ("sol_scout", "agents/sol_scout_live.py"),
    ("eth_scout", "agents/eth_scout_live.py"),
    # Execution pipeline
    ("coordinator", "agent_coordinator_v2.py"),
    ("executor", "agents/execution_bot_v3.py"),
    ("risk_manager", "agents/risk_manager.py"),
    # Analysis layer
    ("auditor", "agents/auditor.py"),
]

BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"
RUNNING = True
processes = {}

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] SUPERVISOR: {msg}")

def signal_handler(signum, frame):
    global RUNNING
    log("Shutdown signal received, stopping all agents...")
    RUNNING = False
    for name, proc in processes.items():
        try: proc.terminate()
        except: pass
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def start_agent(name, script):
    log_file = LOG_DIR / f"{name}.log"
    proc = subprocess.Popen(
        [sys.executable, str(BASE_DIR / script)],
        stdout=open(log_file, "a"),
        stderr=subprocess.STDOUT,
        cwd=str(BASE_DIR),
        start_new_session=True
    )
    return proc

def main():
    global RUNNING
    LOG_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "signals").mkdir(exist_ok=True)
    (DATA_DIR / "trades").mkdir(exist_ok=True)
    
    log("="*60)
    log("🚀 TRADING AGENT ARMY SUPERVISOR STARTING")
    log("="*60)
    
    # Start all agents
    for name, script in AGENTS:
        try:
            processes[name] = start_agent(name, script)
            log(f"Started {name} (PID {processes[name].pid})")
            time.sleep(0.5)
        except Exception as e:
            log(f"ERROR starting {name}: {e}")
    
    log(f"All {len(processes)} agents deployed")
    log("Monitoring health every 5 seconds...")
    log("Press Ctrl+C to shutdown gracefully")
    
    restart_count = {name: 0 for name, _ in AGENTS}
    
    while RUNNING:
        try:
            for name, proc in list(processes.items()):
                if proc.poll() is not None:  # Process died
                    restart_count[name] += 1
                    log(f"⚠️  {name} died (exit {proc.returncode}), restarting ({restart_count[name]}x)...")
                    processes[name] = start_agent(name, next(s for n,s in AGENTS if n == name))
                    log(f"✅ {name} restarted (PID {processes[name].pid})")
            
            # Status report every 60 seconds
            if int(time.time()) % 60 == 0:
                alive = sum(1 for p in processes.values() if p.poll() is None)
                log(f"Status: {alive}/{len(processes)} agents alive")
            
            time.sleep(5)
        except KeyboardInterrupt:
            break
        except Exception as e:
            log(f"Supervisor error: {e}")
            time.sleep(5)
    
    log("Shutdown complete")

if __name__ == '__main__':
    main()
