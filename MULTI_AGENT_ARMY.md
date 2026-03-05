# Multi-Agent Trading Army

## Architecture: Distributed Autonomous Trading System

### Agent Types

#### 1. Signal Scouts (Data Collectors)
**Count:** 5-10 agents  
**Role:** Monitor multiple timeframes and assets for liquidity sweeps
**Assets:** BTC, ETH, SOL, AVAX, MATIC
**Timeframes:** 1m, 5m, 15m, 1h
**Outputs:** Raw sweep signals with confidence scores

```yaml
scouts:
  - name: BTC-1M-Scout
    asset: BTC-USD
    timeframe: 1m
    params:
      sweep_lookback: 15
      wick_ratio: 1.8
      volume_threshold: 1.3
  
  - name: SOL-1M-Scout
    asset: SOL-USD
    timeframe: 1m
    params:
      sweep_lookback: 10  # SOL more volatile
      wick_ratio: 1.5
      volume_threshold: 1.2
```

#### 2. Trend Analysts (Confluence Checkers)
**Count:** 3 agents  
**Role:** Verify higher timeframe alignment
**Checks:**
- 15m trend direction (EMA alignment)
- 1h trend direction
- Daily support/resistance levels
- Regime classification (trending/ranging/vol)

```yaml
analysts:
  - name: HTF-Trend-Analyst
    timeframes: [15m, 1h, 4h]
    indicators: [EMA, ADX, Volume Profile]
    
  - name: Regime-Analyst
    regimes: [trending, ranging, high_vol, low_vol]
    adjustments_by_regime: true
```

#### 3. Risk Managers (Position Sizers)
**Count:** 2 agents  
**Role:** Calculate position sizes and manage portfolio risk
**Rules:**
- Kelly Criterion sizing
- Correlation checks (don't double up)
- Daily loss limits (5% hard stop)
- Position caps (max 2 concurrent)

```yaml
risk_managers:
  - name: Primary-Risk
    max_daily_loss: 0.05
    max_concurrent: 2
    kelly_fraction: 0.25  # Conservative half-Kelly
    
  - name: Emergency-Stop
    circuit_breakers:
      - daily_dd > 5%
      - consecutive_losses > 4
      - volatility_spike > 3x
```

#### 4. Execution Bots (Order Managers)
**Count:** 3 agents  
**Role:** Place and manage orders on exchanges
**Strategies:**
- Limit orders when possible (0% maker fee)
- Market orders in fast-moving conditions
- Partial fills management
- Slippage monitoring

```yaml
execution_bots:
  - name: Coinbase-Executor
    exchange: coinbase_advanced
    order_types: [limit, market]
    max_slippage: 0.5%
    
  - name: Backup-Executor
    exchange: kraken  # fallback
    order_types: [limit]
```

#### 5. Performance Auditors (Monitors)
**Count:** 2 agents  
**Role:** Track performance and detect drift
**Metrics:**
- Win rate vs backtest
- Sharpe ratio
- Max drawdown
- Signal accuracy
- Latency tracking

```yaml
auditors:
  - name: Realtime-Auditor
    check_interval: 1h
    alerts:
      - win_rate < 30%
      - drawdown > 10%
      - latency > 500ms
      
  - name: Daily-Reporter
    schedule: daily 6pm
    reports:
      - pnl_summary
      - trade_log
      - deviation_analysis
```

### Communication Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Signal      │────▶│ Trend       │────▶│ Risk        │
│ Scouts      │     │ Analysts    │     │ Managers    │
│ (detect)    │     │ (validate)  │     │ (size)      │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Performance │◀────│ Execution   │◀────│ Approved    │
│ Auditors    │     │ Bots        │     │ Trades      │
│ (monitor)   │     │ (execute)   │     │ (queue)     │
└─────────────┘     └─────────────┘     └─────────────┘
```

### Decision Consensus

**Trade Execution Requires:**
- 2+ Signal Scouts agree on sweep
- 1+ Trend Analyst confirms alignment
- Risk Manager approves size
- Circuit breaker not triggered

**Example Flow:**
1. BTC-1M-Scout detects sweep → confidence 0.85
2. SOL-1M-Scout also signals → cross-asset correlation check
3. HTF-Trend-Analyst confirms 15m uptrend
4. Risk Manager calculates: 2% risk = $200 position
5. Coinbase-Executor places limit order
6. Realtime-Auditor logs trade, checks latency < 200ms

### Scaling

**Phase 1:** 5 agents (1 scout per asset)
**Phase 2:** 10 agents (multiple timeframes)
**Phase 3:** 20+ agents (additional assets, backup exchanges)

### Failover

- If Primary-Risk goes down → Emergency-Stop activates
- If Coinbase-Executor fails → Backup-Executor takes over
- If scouts disagree → No trade (require consensus)
- If auditors detect drift → Auto-pause, human review

### Technology Stack

- **Agents:** OpenClaw sub-agents (sessions_spawn)
- **Communication:** Redis/pub-sub or shared state files
- **Execution:** Coinbase Advanced Trade API
- **Monitoring:** Telegram alerts + daily reports
- **State:** JSON files with locking

### Deployment

```bash
# Start the army
openclaw agent start --config trading_army.yaml

# Monitor
openclaw agent status

# Emergency stop
openclaw agent broadcast --signal HALT
```
