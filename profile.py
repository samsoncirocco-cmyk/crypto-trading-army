#!/usr/bin/env python3
"""
Performance Profiler - Monitor agent resource usage
"""
import os, time, json, psutil
from datetime import datetime, timezone
from pathlib import Path

def profile_agents():
    """Profile all trading agent processes"""
    print("="*60)
    print("📊 PERFORMANCE PROFILE")
    print("="*60)
    
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info']):
        try:
            cmd = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
            if 'scout' in cmd or 'executor' in cmd or 'coordinator' in cmd:
                processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cmd': cmd[:60],
                    'cpu': proc.info['cpu_percent'],
                    'memory_mb': proc.info['memory_info'].rss / 1024 / 1024
                })
        except: pass
    
    if not processes:
        print("   No agents currently running")
        return
    
    total_cpu = 0
    total_mem = 0
    
    for p in processes:
        print(f"   PID {p['pid']}: {p['cpu']:.1f}% CPU, {p['memory_mb']:.1f}MB | {p['cmd'][:40]}")
        total_cpu += p['cpu']
        total_mem += p['memory_mb']
    
    print(f"\n   Total: {total_cpu:.1f}% CPU, {total_mem:.1f}MB RAM")
    print(f"   System: {psutil.cpu_percent()}% CPU, {psutil.virtual_memory().percent}% RAM")
    
    # Save report
    report = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'processes': len(processes),
        'total_cpu': total_cpu,
        'total_memory_mb': total_mem,
        'system_cpu': psutil.cpu_percent(),
        'system_ram': psutil.virtual_memory().percent
    }
    
    with open('performance_report.json', 'a') as f:
        f.write(json.dumps(report) + '\n')

if __name__ == '__main__':
    profile_agents()
