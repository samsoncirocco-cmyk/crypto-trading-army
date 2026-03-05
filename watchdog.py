#!/usr/bin/env python3
"""
Agent Army Watchdog - Persistent restarter
Runs independently, monitors agents, restarts if dead.
"""
import fcntl
import subprocess
import sys
import time
from pathlib import Path

AGENTS = [
    ("btc_scout", "agents/btc_scout_robust.py"),
    ("sol_scout", "agents/sol_scout_robust.py"),
    ("eth_scout", "agents/eth_scout.py"),
    ("trend_analyst", "agents/trend_analyst.py"),
    ("risk_manager", "agents/risk_manager.py"),
    ("executor", "agents/execution_bot.py"),
    ("coordinator", "agent_coordinator.py"),
]

BASE_DIR = Path.home() / ".openclaw/workspace/execution/trading"
LOCK_DIR = BASE_DIR / "data" / "locks"
LOCK_DIR.mkdir(parents=True, exist_ok=True)
LOCK_FILE = LOCK_DIR / "watchdog.lock"


def acquire_lock():
    handle = LOCK_FILE.open("w")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Watchdog already running, exiting.")
        sys.exit(0)
    handle.write("watchdog\n")
    handle.flush()
    return handle


def script_pattern(script):
    return str((BASE_DIR / script).resolve())


def is_running(script):
    result = subprocess.run(["pgrep", "-f", script_pattern(script)], capture_output=True)
    return result.returncode == 0


def start_agent(name, script):
    log = BASE_DIR / "logs" / f"{name}.log"
    proc = subprocess.Popen(
        ["python3", str((BASE_DIR / script).resolve())],
        stdout=open(log, "a"),
        stderr=subprocess.STDOUT,
        cwd=str(BASE_DIR),
        start_new_session=True,
    )
    return proc.pid


LOCK_HANDLE = acquire_lock()

print("WATCHDOG STARTED - Monitoring agent army...")
print("Press Ctrl+C to stop\n")

try:
    while True:
        for name, script in AGENTS:
            if not is_running(script):
                pid = start_agent(name, script)
                print(f"RESTARTED: {name} (PID {pid})")
        time.sleep(10)
except KeyboardInterrupt:
    print("\nWatchdog stopped")
