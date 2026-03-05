#!/usr/bin/env python3
"""
Advanced Executor - TWAP, VWAP, Iceberg orders
"""
import time
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class ExecutionSlice:
    timestamp: str
    size: float
    price: float
    filled: bool = False

class TWAPExecutor:
    """Time-Weighted Average Price execution"""
    
    def __init__(self, total_size: float, duration_minutes: int, num_slices: int = 10):
        self.total_size = total_size
        self.duration = duration_minutes
        self.num_slices = num_slices
        self.slice_size = total_size / num_slices
        self.interval = (duration_minutes * 60) / num_slices
        self.slices: List[ExecutionSlice] = []
        self.completed = []
    
    def generate_schedule(self):
        """Generate TWAP schedule"""
        now = datetime.now(timezone.utc)
        for i in range(self.num_slices):
            slice_time = now.timestamp() + (i * self.interval)
            self.slices.append(ExecutionSlice(
                timestamp=datetime.fromtimestamp(slice_time, timezone.utc).isoformat(),
                size=self.slice_size,
                price=0
            ))
        return self.slices
    
    def execute_twap(self, client, symbol: str, side: str):
        """Execute TWAP order"""
        print(f"🕐 TWAP: {self.num_slices} slices over {self.duration}min")
        
        results = []
        for i, slice_order in enumerate(self.slices):
            # Wait for scheduled time
            target_time = datetime.fromisoformat(slice_order.timestamp)
            wait_seconds = (target_time - datetime.now(timezone.utc)).total_seconds()
            
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            
            # Get current price
            try:
                price = client.get_product_price(symbol)
            except:
                price = 0
            
            print(f"   Slice {i+1}/{self.num_slices}: ${slice_order.size:.2f} @ ${price:.2f}")
            
            results.append({
                'slice': i + 1,
                'size': slice_order.size,
                'price': price,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            
            # Brief pause between slices (except last)
            if i < len(self.slices) - 1:
                time.sleep(1)
        
        return results

class VWAPExecutor:
    """Volume-Weighted Average Price execution"""
    
    def __init__(self, total_size: float, target_vwap_deviation: float