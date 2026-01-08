# Testing Mode Guide

## What is Testing Mode?

Testing mode is a **simulation mode** that allows you to verify strategy profitability without risking any capital. Unlike paper trading (which simulates execution), testing mode:

- ✅ **Logs all potential trades** without executing them
- ✅ **Tracks actual market outcomes** to verify if trades would have been profitable
- ✅ **Calculates hypothetical PnL** based on real market resolutions
- ✅ **Generates detailed reports** with win rates, profits, and performance metrics
- ✅ **Exports data to CSV** for further analysis

This is the **safest way** to validate your strategies before using real funds.

## Quick Start

### 1. Enable Testing Mode

Edit `.env`:
```env
TESTING_MODE=true
ENABLE_LIVE_TRADING=false  # Must be false
```

Or edit `config/config.yaml`:
```yaml
testing:
  enabled: true
  output_dir: "simulation_results"
  monitor_interval: 30  # Check for resolutions every 30 seconds
  generate_reports: true
```

### 2. Run the Bot

```bash
python run_bot.py
```

You'll see:
```
🧪 TESTING MODE - Trades will be logged and verified (NO execution)
🧪 Testing Mode Active - Simulation session: sim_1736248245
📊 Results will be saved to: simulation_results/sim_1736248245.jsonl
```

### 3. Monitor Progress

Every few minutes, you'll see status updates:

```
🧪 Testing Mode Statistics:
  Total Simulated Trades: 15
  Resolved: 8, Pending: 7
  Win Rate: 87.50%
  Hypothetical PnL: $145.23
  Avg PnL/Trade: $18.15
```

### 4. View Results

When you stop the bot (Ctrl+C), it automatically generates:

1. **Final Report**: `simulation_results/sim_XXXXX_report.txt`
   - Overall statistics
   - Strategy breakdown
   - Win rates and PnL

2. **Trade Log**: `simulation_results/sim_XXXXX.jsonl`
   - JSONL format (one trade per line)
   - Complete trade details

3. **CSV Export**: `simulation_results/sim_XXXXX_trades.csv`
   - Import into Excel/Google Sheets
   - Analyze with pandas/R

## How It Works

### Logging Trades

When a strategy identifies an opportunity, instead of executing:

```python
# NORMAL MODE: Executes trade on Polymarket
order = client.create_market_order(...)

# TESTING MODE: Logs the trade
simulated_trade = trade_simulator.log_trade(
    strategy="LatencyArbitrage",
    market_id="...",
    token_id="...",
    entry_price=0.52,
    amount=192.31,  # $100 / 0.52
    outcome="UP",
    edge=0.035  # 3.5% edge
)
```

You'll see:
```
📝 SIMULATED TRADE: LatencyArbitrage - BUY UP @ 0.520 (Edge: 3.50%, Amount: $100.00)
   Market: Will BTC go up in the next 15 minutes?
```

### Monitoring Outcomes

The bot continuously monitors simulated trades:

1. **Checks market prices** every 30 seconds (configurable)
2. **Detects resolution** when price reaches 0.99 (YES) or 0.01 (NO)
3. **Calculates actual PnL** based on resolution
4. **Updates statistics** in real-time

```
✅ TRADE RESOLVED: LatencyArbitrage_1736248245 - Outcome: YES
   (PnL: $47.06, ROI: +47.06%)
```

### Generating Reports

Reports show exactly what would have happened:

```
=============================================================
SIMULATION PERFORMANCE REPORT
=============================================================
Session ID: sim_1736248245
Duration: 2026-01-07 15:30:42

Overall Statistics:
  Total Simulated Trades: 25
  Resolved Trades: 20
  Pending/Monitoring: 5

  Winning Trades: 18
  Losing Trades: 2
  Win Rate: 90.00%

  Total PnL: $425.67
  Average PnL/Trade: $21.28

Strategy Performance:

  LatencyArbitrage:
    Trades: 12
    Win Rate: 91.67%
    Total PnL: $312.45

  BinaryHedging:
    Trades: 8
    Win Rate: 87.50%
    Total PnL: $113.22
=============================================================
```

## Configuration Options

### In config/config.yaml

```yaml
testing:
  enabled: true  # Enable testing mode
  output_dir: "simulation_results"  # Where to save results
  monitor_interval: 30  # How often to check resolutions (seconds)
  auto_resolve_timeout: 3600  # Auto-expire trades after 1 hour
  generate_reports: true  # Generate periodic reports
```

### Testing vs Other Modes

| Mode | Executes Trades | Tracks Outcomes | Verifies Profit | Use Case |
|------|----------------|-----------------|-----------------|----------|
| **Testing** | ❌ No | ✅ Yes | ✅ Yes | Validate strategies |
| **Paper Trading** | ❌ No | ❌ No | ❌ No | Practice execution |
| **Live Trading** | ✅ Yes | ✅ Yes | ✅ Yes | Real trading |

## Use Cases

### 1. Strategy Validation

Run for 24-72 hours to verify strategy performance:

```bash
# Enable latency arbitrage only
vim config/config.yaml  # Set other strategies to enabled: false
TESTING_MODE=true python run_bot.py
```

After 24 hours, check:
- Win rate (target: 85%+)
- Average PnL per trade
- Frequency of opportunities

### 2. Parameter Tuning

Test different edge thresholds:

```yaml
strategies:
  latency_arbitrage:
    min_edge: 0.02  # Try 2%, then 3%, then 4%
```

Compare results across multiple test runs.

### 3. Market Selection

Test which markets are most profitable:

```yaml
strategies:
  latency_arbitrage:
    markets:
      - "BTC_15min"  # Test BTC only first
```

Then test ETH, then SOL, compare results.

### 4. Long-term Performance

Run for a week to account for:
- Different market conditions
- Volatile vs calm periods
- Various times of day

## Analyzing Results

### Using the CSV Export

```python
import pandas as pd

# Load results
df = pd.read_csv('simulation_results/sim_1736248245_trades.csv')

# Filter to resolved trades
resolved = df[df['status'] == 'RESOLVED']

# Calculate metrics
print(f"Win Rate: {(resolved['net_pnl'] > 0).mean():.2%}")
print(f"Avg Profit: ${resolved['net_pnl'].mean():.2f}")
print(f"Max Win: ${resolved['net_pnl'].max():.2f}")
print(f"Max Loss: ${resolved['net_pnl'].min():.2f}")

# Group by strategy
by_strategy = resolved.groupby('strategy')['net_pnl'].agg(['count', 'mean', 'sum'])
print(by_strategy)
```

### Checking Trade Log (JSONL)

```python
import json

# Read all trades
with open('simulation_results/sim_1736248245.jsonl') as f:
    trades = [json.loads(line) for line in f]

# Find best trade
best = max(trades, key=lambda t: t.get('net_pnl', 0))
print(f"Best trade: {best['outcome']} - ${best['net_pnl']:.2f}")

# Find trades with high edge
high_edge = [t for t in trades if t.get('edge', 0) > 0.05]
print(f"Found {len(high_edge)} trades with 5%+ edge")
```

## Best Practices

### 1. Start with Testing Mode

Always test first:
1. ✅ Run in testing mode for 24-48 hours
2. ✅ Verify win rate > 80%
3. ✅ Check average PnL positive
4. ✅ Review edge cases and failures
5. ✅ Then move to paper trading
6. ✅ Finally, live trading with small positions

### 2. Run Multiple Sessions

Compare results across different periods:
- Volatile market days
- Calm market days
- Different times (US hours vs Asia hours)
- Weekdays vs weekends

### 3. Document Your Findings

Keep notes:
```
Session: sim_1736248245
Date: 2026-01-07
Markets: BTC_15min only
Conditions: High volatility (+3% BTC move)
Results: 15 trades, 93% win rate, $312 profit
Notes: Strategy performs best during volatile periods
```

### 4. Iterate and Improve

Use results to refine:
- Increase min_edge if win rate too low
- Decrease min_edge if missing opportunities
- Adjust position sizes based on edge
- Filter out low-confidence setups

## Troubleshooting

### "No trades being logged"

- Check that opportunities are being found: Look for "OPPORTUNITY FOUND" in logs
- Verify markets are active: 15-min crypto markets may not always exist
- Lower edge thresholds temporarily to see if opportunities appear
- Ensure price feeds are connected (for latency arbitrage)

### "Trades never resolving"

- 15-minute markets resolve quickly (~15 minutes)
- Check `monitor_interval` isn't too long (30s recommended)
- Verify bot is still running and checking
- Some markets may take longer to settle

### "Results seem unrealistic"

Testing mode assumptions:
- Assumes you can buy at the logged price (may have slippage in reality)
- Doesn't account for gas fees
- Assumes market has sufficient liquidity
- Resolution is binary (0 or 1), real settlements may vary

Use results as an **upper bound** on performance.

## Next Steps

After successful testing:

1. ✅ **Reviewed results**: Win rate good, PnL positive
2. ➡️ **Switch to paper trading**: Set `TESTING_MODE=false`, `ENABLE_LIVE_TRADING=false`
3. ➡️ **Monitor for 24 hours**: Verify execution works as expected
4. ➡️ **Start small**: Set `max_position_size_usd: 50`
5. ➡️ **Go live carefully**: `ENABLE_LIVE_TRADING=true`
6. ➡️ **Scale gradually**: Increase position sizes as confidence grows

---

**Testing mode gives you data-driven confidence before risking real capital!** 🧪📊

