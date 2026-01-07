# Polymarket Multi-Strategy Trading Bot

A comprehensive, production-ready trading bot for Polymarket that implements multiple profitable strategies based on research of successful bots that have generated millions in profits.

## 🎯 Strategies Implemented

Based on extensive research of the most profitable Polymarket bots in 2025-2026:

### 1. **Temporal/Latency Arbitrage** (Highest Profit Potential)
- **How it works**: Exploits lag between spot crypto prices on exchanges (Binance, Coinbase) and Polymarket's 15-minute markets
- **Success rate**: 98% win rate documented
- **Example**: Bot turned $313 into $438,000 in one month using this strategy
- **Targets**: BTC, ETH, SOL 15-minute up/down markets

### 2. **Binary Market Hedging**
- **How it works**: Buys underpriced outcomes in binary markets when temporary mispricings occur
- **Example**: Trader "gabagool" paid 96.6 cents for contracts guaranteed to be worth $1
- **Strategy**: Asymmetric buying at different timestamps when markets misprice

### 3. **Combinatorial Arbitrage**
- **How it works**: Exploits inconsistencies between related markets
- **Revenue**: ~$40M earned between April 2024-2025 using this strategy
- **Approach**: Finds markets where probabilities don't add up correctly

### 4. **Market Making**
- **How it works**: Provides liquidity by placing orders on both sides, profiting from spread
- **Target**: Low-volatility markets with 2.5%+ spreads
- **Approach**: Multi-timeframe volatility analysis (3h, 24h, 7d, 30d)

### 5. **AI-Powered Predictions** (Template)
- **Potential**: $2.2M generated in 2 months by documented bot
- **Approach**: Ensemble models trained on news and social data
- **Status**: Framework included, requires training data

## 📊 Performance Metrics

Based on research findings:
- **Bot average**: $206,000 profit with 85%+ win rate
- **Best case**: $438,000 from $313 (98% win rate in 30 days)
- **vs Humans**: Bots consistently outperform by 2x due to speed and consistency

## 🏗️ Architecture

```
polymarket_bot/
├── bot.py                      # Main orchestrator
├── clients/
│   └── polymarket_client.py    # Polymarket API wrapper
├── data_feeds/
│   └── exchange_feeds.py       # Real-time price feeds (Binance, etc.)
├── strategies/
│   ├── base_strategy.py        # Base strategy class
│   ├── latency_arbitrage.py   # Temporal arbitrage
│   ├── binary_hedging.py       # Binary market hedging
│   ├── combinatorial_arbitrage.py
│   └── market_making.py
├── models/
│   └── position.py             # Position tracking models
└── utils/
    ├── config.py               # Configuration management
    ├── logger.py               # Logging setup
    └── risk_manager.py         # Risk management
```

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
cd polymarket_bot

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your credentials
nano .env
```

### 3. Choose Your Mode

The bot has **three operating modes**:

#### 🧪 Testing Mode (RECOMMENDED FIRST!)
- Logs potential trades without executing
- Tracks actual outcomes to verify profitability
- Generates reports with real performance data
- **Perfect for validating strategies before risking capital**

```env
TESTING_MODE=true
ENABLE_LIVE_TRADING=false
```

📖 **See [TESTING_MODE.md](TESTING_MODE.md) for complete guide**

#### 📊 Paper Trading Mode
- Simulates execution without real funds
- Practice bot operation
- No outcome tracking

```env
TESTING_MODE=false
ENABLE_LIVE_TRADING=false
```

#### ⚠️ Live Trading Mode
- Executes real trades with real funds
- Only use after thorough testing!

```env
TESTING_MODE=false
ENABLE_LIVE_TRADING=true
```

**Required credentials:**
- `POLYMARKET_PRIVATE_KEY`: Your Ethereum private key
- `BINANCE_API_KEY`: For price feeds (latency arbitrage)
- `BINANCE_API_SECRET`: For price feeds

**Important settings:**
- `ENABLE_LIVE_TRADING`: Set to `false` for paper trading, `true` for live
- `MAX_POSITION_SIZE`: Maximum USD per position (default: $1000)
- `RISK_PER_TRADE`: Risk percentage per trade (default: 2%)

### 4. Run the Bot

```bash
# Testing mode (RECOMMENDED FIRST!)
# Set TESTING_MODE=true in .env
python run_bot.py

# Paper trading mode
# Set both TESTING_MODE=false and ENABLE_LIVE_TRADING=false
python run_bot.py

# Live trading (after thorough testing!)
# Set ENABLE_LIVE_TRADING=true in .env
python run_bot.py
```

## ⚙️ Configuration

Edit `config/config.yaml` to customize:

### Trading Parameters
```yaml
trading:
  max_position_size_usd: 1000
  risk_per_trade: 0.02  # 2% per trade
  min_profit_threshold: 0.025  # 2.5% minimum
  max_slippage: 0.005
```

### Strategy Selection
```yaml
strategies:
  latency_arbitrage:
    enabled: true
    priority: 1
    min_edge: 0.03  # 3% minimum edge

  binary_hedging:
    enabled: true
    priority: 2
    min_discount: 0.034  # 3.4% minimum discount

  combinatorial_arbitrage:
    enabled: true
    priority: 3
    min_edge: 0.02

  market_making:
    enabled: true
    priority: 4
    min_spread: 0.025  # 2.5% minimum spread
```

### Risk Management
```yaml
risk_management:
  max_total_exposure_usd: 10000
  max_positions: 20
  max_loss_per_day_usd: 500
  emergency_stop_loss_pct: 0.1  # 10% drawdown stops bot
```

## 📈 Strategy Details

### Latency Arbitrage Implementation

```python
# Monitors BTC/ETH/SOL prices on Binance
# When price moves 1%+, checks Polymarket odds
# If Polymarket still shows ~50/50, buys the likely outcome
# Exits when odds update or market resolves

# Example:
# BTC moves +2% on Binance → 85% probability of "UP"
# Polymarket still shows 0.50 → Buy UP at 0.50
# Exit when price updates to 0.80+ or market resolves
```

### Binary Hedging Implementation

```python
# Monitors binary markets for mispricings
# Looks for:
#   1. YES + NO ≠ 1.00 (sum arbitrage)
#   2. Price below recent average (mean reversion)

# Example:
# YES = 0.48, NO = 0.48 (sum = 0.96)
# Buy both → guaranteed 4% profit when market resolves
```

### Combinatorial Arbitrage Implementation

```python
# Groups related markets
# Checks if probabilities are consistent
# If inconsistent, executes multi-leg arbitrage

# Example:
# Market A: Candidate wins = 40%
# Market B: Candidate loses = 55%
# Total = 95% → Buy both for 5% edge
```

## 🛡️ Risk Management Features

1. **Position Limits**: Max positions, max exposure per position
2. **Daily Loss Limits**: Stop trading if daily loss exceeds threshold
3. **Emergency Stop**: Automatic shutdown on 10% total drawdown
4. **Position Sizing**: Kelly Criterion-inspired sizing
5. **Real-time Monitoring**: Continuous position monitoring and risk checks

## 📊 Monitoring & Logging

The bot provides comprehensive logging:

```
2026-01-07 10:30:45.123 | INFO | Strategy Update
BTC_15min: UP 2.35% (confidence: 0.85)
OPPORTUNITY FOUND: BTC_15min UP - Edge: 3.20% (Price: 0.520)
Position opened successfully: latency_1736248245

Bot Status Update
=============================================================
Balance: $1,234.56 (Start: $1,000.00)
PnL: $234.56 (+23.46%)
Total Exposure: $850.00 (8.5%)
Today PnL: $87.23

Strategy Performance:
  LatencyArbitrage: Trades: 15, Win Rate: 93.3%, PnL: $185.45
  BinaryHedging: Trades: 8, Win Rate: 87.5%, PnL: $62.31
```

## ⚠️ Important Notes

### Market Changes (2025-2026)
- Polymarket introduced **taker fees on 15-minute crypto markets**
- Fees were specifically "directed against high-frequency bots"
- Latency arbitrage strategy accounts for these fees
- Still profitable with proper edge thresholds

### Best Practices
1. **Start with paper trading** (ENABLE_LIVE_TRADING=false)
2. **Test with small position sizes** initially
3. **Monitor for at least 24 hours** before scaling up
4. **Review logs regularly** for any errors
5. **Keep API credentials secure** (never commit .env file)

### Infrastructure Requirements
- **Latency**: Sub-500ms recommended for latency arbitrage
- **Uptime**: 24/7 operation recommended
- **VPS**: Consider cloud hosting for reliability
- **Monitoring**: Set up alerts for downtime

## 🔧 Technical Requirements

- **Python**: 3.9+
- **Dependencies**: See requirements.txt
- **APIs**:
  - Polymarket CLOB API
  - Binance WebSocket API (for latency arbitrage)
- **Blockchain**:
  - Polygon (MATIC) for gas fees
  - USDC for trading

## 📚 Research Sources

This bot is based on research from:
- Trading bot that turned $313 into $438k analysis
- "Inside the Mind of a Polymarket BOT" study
- Polymarket HFT arbitrage research
- Top 10 strategies used by successful traders
- Official Polymarket documentation

## 🤝 Contributing

This is a research and educational project. Improvements welcome:
- Additional strategies
- Better risk management
- ML model implementations
- Performance optimizations

## ⚖️ Disclaimer

**This bot is for educational and research purposes.**

- Trading involves risk of loss
- Past performance does not guarantee future results
- Always test with paper trading first
- Use at your own risk
- Consult with financial advisors before trading

## 📄 License

MIT License - Use at your own risk

## 🆘 Support

For issues or questions:
1. Check logs in `logs/polymarket_bot.log`
2. Review configuration in `config/config.yaml`
3. Verify API credentials in `.env`
4. Check Polymarket API status

---

**Built with research from the most successful Polymarket bots of 2025-2026**

**Start small. Test thoroughly. Scale carefully.** 🚀
